# Jarvis UI redesign + Gemini retry — design

Date: 2026-09-15
Status: approved in brainstorming, awaiting spec review

## Problem

1. **UI looks dated and is hard to read.** Discord-gray palette with one dull accent,
   fonts 9–12 pt, 20 pt header, square flat `tk.Button`s, plain `tk.Text` transcript
   with no bubbles.
2. **Compact mode is broken.** Header keeps two long Thai text buttons, composer does
   not shrink, `minsize(420, 430)` is fixed, sidebar only hides on manual toggle.
   Nothing responds to window width.
3. **Mixed languages.** Errors from `brain.py` (e.g. `Gemini returned HTTP 503. Try again later.`)
   have no Thai entry in `thai.py`, so English appears inside a Thai UI.
4. **Gemini 503 fails immediately.** HTTP 503 means Google's model is temporarily
   overloaded. `brain._post` raises on the first failure; no retry.

## Goals

- Modern, vibrant dark theme ("Insta Sunset", solid colors, no gradients).
- Readable text: nothing below 12 pt, body 15 pt, DPI-aware.
- Responsive layout that works from a 360 px wide floating window to full screen.
- All user-facing text in Thai.
- Transient Gemini 5xx errors retried automatically, cancellable with Stop/Esc.

## Non-goals

- No change to the approval boundary, action policy, screen control logic, Discord
  rules, voice pipeline or local storage.
- No automatic fallback model (add later if 503s persist).
- No light theme.
- No gradients (user declined).
- No web/HTML UI.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| UI toolkit | CustomTkinter (pip `customtkinter`) | Rounded widgets, DPI scaling, keeps all Python logic and most tests. Chosen over pywebview (bigger rewrite) and plain Tk restyle (dated ceiling). |
| Palette | Insta Sunset, solid | Chosen from mockups (Arc Reactor, Neon Violet, Aurora, Lobster Red, Insta Sunset). |
| Font | Leelawadee UI | Ships with Windows, renders Thai well. |
| Responsive breakpoint | 720 px window width | Below: sidebar hidden, icon header. |

## 1. Visual system — `theme.py` (new)

Single source for colors, fonts and sizes. No hex values elsewhere in `app.py`.

### Colors

| Token | Hex | Use |
|---|---|---|
| `BG` | `#0C0A12` | Window background |
| `SIDEBAR` | `#14101D` | Sidebar, pending bar, dialog background |
| `SURFACE` | `#201A2C` | Jarvis bubbles, composer, nav buttons, inputs |
| `SURFACE_HI` | `#2C2340` | Icon buttons, hover on surface items |
| `TEXT` | `#F7F2FA` | Primary text |
| `MUTED` | `#B8AFC6` | Hints, secondary text (≥ 4.5:1 on `BG`) |
| `PRIMARY` | `#D62976` | User bubbles, primary buttons (new chat, send, review, approve, save) |
| `PRIMARY_HOVER` | `#E1306C` | Hover for primary |
| `ON_PRIMARY` | `#FFFFFF` | Text on primary |
| `ORANGE` | `#F77737` | "Jarvis" sender label, icon glyphs |
| `PURPLE` | `#833AB4` | Focus border on inputs/composer |
| `SUCCESS` | `#34D399` | Ready pill text, key-connected dot |
| `SUCCESS_BG` | `#0B3326` | Ready pill background |
| `WARN` / `WARN_BG` | `#FBBF24` / `#3A2A0A` | Warnings, retry notices, Discord risk warning |
| `DANGER` | `#F87171` | Error notices |

### Typography (points, CustomTkinter-scaled)

| Token | Size / weight | Use |
|---|---|---|
| `TITLE` | 24 bold | Main header, brand name |
| `HEADING` | 18 bold | Dialog titles |
| `BODY` | 15 | Chat bubbles, composer, inputs, dialog body |
| `LABEL` | 13 | Buttons, nav items, sender names (bold), pills |
| `HINT` | 12 | Shortcut hint, footnotes. Minimum size anywhere. |

### Shape and spacing

- Corner radius: buttons/nav 10, bubbles and composer 16, pills fully round, dialog inputs 10.
- Spacing on a 4/8 rhythm: 8 between related items, 12–16 section padding, 24 main
  padding in full mode, 12 in narrow mode.
- Icon buttons 38×38; click targets ≥ 38 px.
- `customtkinter.set_appearance_mode("dark")`; widget colors always passed from `theme.py`.

## 2. Layout — `app.py`

### Full mode (window width ≥ 720 px)

```
┌─────────────┬──────────────────────────────────────────────┐
│ [logo]Jarvis│ แชตกับ Jarvis           ● พร้อม   [⤡] [■]   │
│ ผู้ช่วยส่วนตัว │                                              │
│             │ ╭ Jarvis ───────────────╮                    │
│ [+ แชตใหม่]  │ │ สวัสดี วันนี้อยาก...  │ [คัดลอก]           │
│  สรุปข้อความ  │ ╰───────────────────────╯                    │
│  ควบคุมคอม   │                   ╭──────────────────────╮   │
│  Discord    │                   │ เปิดเพลงใน Spotify   │   │
│  ตั้งค่า AI   │                   ╰──────────────────────╯   │
│             │ ⚠ Gemini ไม่ว่าง กำลังลองใหม่ (2/3)…          │
│             │ ┌ รออนุญาต 1 รายการ ─────────── [ตรวจสอบ] ┐   │
│ ● คีย์พร้อม   │ ╭ พิมพ์ข้อความ… ──────────────╮ [●] [➤]      │
│ [โฟลเดอร์]   │ Enter ส่ง · Shift+Enter ขึ้นบรรทัด · Esc หยุด  │
└─────────────┴──────────────────────────────────────────────┘
```

- **Sidebar** (`CTkFrame`, width 220, `SIDEBAR`): logo from `jarvis.ico` rendered to a
  40×40 `CTkImage` via Pillow + "Jarvis" (`TITLE`); tagline (`HINT`, `MUTED`);
  primary "+ แชตใหม่"; surface nav buttons for summarize, PC actions, Discord, AI
  settings; bottom: connection status (green dot when key set) and "เปิดโฟลเดอร์โปรแกรม".
- **Header**: title (`TITLE`), status pill, icon buttons for compact toggle (⤡/⤢) and
  stop (■). Each icon button has a hover tooltip with its Thai name.
- **Status**: the old free-text status line becomes a pill plus an optional muted detail line.
  Pill states: ready (green "● พร้อม"), thinking (orange "กำลังคิด…"), listening (pink
  "กำลังฟัง…"), speaking (orange "กำลังพูด…"), stopped (muted "หยุดแล้ว"). Longer
  guidance text (e.g. dictation-ready hint) shows in the muted detail line under the header.
- **Transcript** (`CTkScrollableFrame`, `BG`): one row per message.
  - Jarvis: left aligned, `SURFACE` bubble, sender label `ORANGE` bold `LABEL`, body `BODY`.
    Small "คัดลอก" text button under the bubble copies its text to the clipboard.
  - User: right aligned, `PRIMARY` bubble, `ON_PRIMARY` text, no sender label.
  - Status: full-width card. Normal: `SURFACE` + `MUTED` text. Warnings/retries:
    `WARN_BG` + `WARN`. Errors: `SURFACE` + `DANGER` text.
  - Right-click on any bubble copies its text.
  - Bubble wrap width = 78 % of transcript width (88 % in narrow mode), recomputed on
    resize (debounced ~100 ms) so text re-wraps.
  - Auto-scroll to bottom after each added message.
  - Transcript keeps at most 200 message rows; oldest rows are destroyed. Model history
    stays capped at 16 entries as today.
- **Pending bar**: `SIDEBAR` frame with 1 px `PRIMARY` border, label "รออนุญาต N รายการ",
  primary "ตรวจสอบ" button. Shown above the composer only when proposals exist
  (same behavior as today).
- **Composer**: rounded `SURFACE` frame, `PURPLE` border while the textbox has focus;
  `CTkTextbox` (3 lines, `BODY`); mic icon button (turns `PRIMARY` while recording);
  primary send ➤ button. Enter sends, Shift+Enter newline, Ctrl+Enter sends (unchanged).
- **Voice row** (full mode only): small "อ่านคำตอบ" button and "อ่านตอบอัตโนมัติ"
  switch under the composer. In narrow mode both live in the ☰ menu.
- **Hint line**: `HINT`, `MUTED`.

### Narrow mode (window width < 720 px)

- Sidebar hidden (`pack_forget()`); header gains a ☰ icon button at left that opens a
  `tk.Menu` styled with theme colors, containing: แชตใหม่, สรุปข้อความ / ไฟล์,
  ควบคุมคอมพิวเตอร์, Discord, ตั้งค่า AI, อ่านคำตอบ, อ่านตอบอัตโนมัติ (checkbutton),
  เปิดโฟลเดอร์โปรแกรม.
- Title becomes logo + "Jarvis" (20 bold). Status pill hides below 440 px width.
- Voice row hidden. Main padding 12. Text sizes unchanged.
- Switching is driven by a `<Configure>` handler on the root window comparing
  `winfo_width()` with 720; it re-packs only when the mode actually changes.

### Compact (floating) toggle

- ⤡ saves current geometry, sets `400x620`, `-topmost` true. Layout changes come from
  the width rule, not from the toggle itself.
- ⤢ restores saved geometry and sets `-topmost` false.
- `minsize(360, 440)` always.

### Dialogs

AI settings, summarize, PC actions, action approval, Discord and screen-step dialogs use
`CTkToplevel` with `SIDEBAR` background, `HEADING` title, `BODY` inputs (`CTkEntry` /
`CTkTextbox`, radius 10, `SURFACE`), `PRIMARY` confirm button and surface cancel button.
Discord risk warning uses `WARN`. Behavior, validation and button labels stay the same.
Default sizes grow ~10 % to fit larger text; all dialogs are resizable.

## 3. Language — `thai.py`

Add Thai entries for every user-facing English string in `app.py` and every
`BrainError` message in `brain.py`, including:

| English key | Thai |
|---|---|
| The API rejected the request. Check the model and API key. | Gemini ปฏิเสธคำขอ ตรวจสอบชื่อโมเดลและ API key |
| The API key was rejected. | API key ไม่ถูกต้อง |
| API access denied. Check the key, project and region. | ไม่มีสิทธิ์ใช้ API ตรวจสอบคีย์ โปรเจกต์ และภูมิภาค |
| That model is unavailable. Choose a model available to your API project. | ไม่พบโมเดลนี้ เลือกโมเดลอื่นในตั้งค่า AI |
| API quota or rate limit reached. Check your Google AI Studio usage. | ใช้โควตา Gemini ครบแล้ว ดูการใช้งานใน Google AI Studio |
| Could not reach Gemini. Check your internet connection and try again. | ติดต่อ Gemini ไม่ได้ ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่ |
| Gemini is busy (HTTP {code}). Try again shortly or change the model in AI settings. | เซิร์ฟเวอร์ Gemini ไม่ว่างตอนนี้ (HTTP {code}) ลองใหม่อีกสักครู่ หรือเปลี่ยนโมเดลในตั้งค่า AI |
| Gemini is busy, retrying ({n}/{total})… | Gemini ไม่ว่าง กำลังลองใหม่ ({n}/{total})… |

Keys with placeholders are translated first, then formatted with `.format(...)`, so
lookup keys stay constant. English keys remain the source strings, as today.

## 4. Gemini retry — `brain.py`

`_post(key, model, body, limit=MAX_RESPONSE, timeout=60, *, on_retry=None, cancelled=None)`

- Retry on HTTP **500, 502, 503, 504** only.
- Up to **3 retries** (4 attempts total). Delay before retry n: 2, 4, 8 s. If the error
  response has a numeric `Retry-After` header, use that instead, capped at 10 s.
- Before each wait, call `on_retry(n, 3)` if provided.
- Wait in 0.1 s slices, checking `cancelled()` if provided; when it returns true, raise
  `BrainError("Stopped")` without making another request (the UI ignores stale generations).
- **Not retried**: 400, 401, 403, 404, 429 (quota; retrying wastes quota), redirects,
  network errors, invalid JSON.
- After the final failed attempt: raise `BrainError` with the "Gemini is busy (HTTP {code})…"
  message, formatted with the last status code.
- `ask`, `ask_screen`, `transcribe` and `synthesize` accept `on_retry` and `cancelled`
  keyword arguments and pass them to `_post`.
- In `app.py`, worker threads pass `cancelled=lambda: generation != self.generation`
  (`self.speech_generation` for dictation/TTS) and an `on_retry` that queues
  `("retry", generation, (n, total))`. `poll()` renders it as a `WARN` status card when the
  generation is current and does not clear `busy`.

## 5. Dependency and launch

- `Start Jarvis.cmd`: after finding `pyw`, run `py -3 -c "import customtkinter"`; if that
  fails, run `py -3 -m pip install --user customtkinter`. If install fails, print
  "ติดตั้ง customtkinter ไม่สำเร็จ ลองรัน: py -m pip install customtkinter" and pause.
- `README.md`: requirements become "Python 3.12+ with Tkinter, Pillow and customtkinter
  (Start Jarvis.cmd installs customtkinter automatically)". Update button names to the new
  labels. Add a short "When Gemini is busy" note describing retries and Stop.

## 6. Testing

Suite command: `python -m unittest discover -s tests -v`.

`tests/test_ui.py` — updated for CustomTkinter widgets:
- chat proposal / stop / late response (logic unchanged; `pending_label` text check).
- dialogs construct and close (find `CTkToplevel` children).
- exact approval preview and approve button (find by Thai text).
- Discord auto-send only for listed targets (unchanged).
- stop cancels screen task (unchanged).
- compact toggle keeps input text, sets and clears topmost, restores geometry.
- **new**: layout at width 600 hides sidebar and shows ☰; width 1000 restores sidebar.
- **new**: current-generation `("retry", …, (2, 3))` event adds one warning card and keeps
  `busy`; stale generation adds nothing.
- **new**: adding 205 messages leaves 200 rows.

`tests/test_boundaries.py` — new tests using the existing
`patch("brain.request.build_opener")` pattern, with sleep patched so tests run instantly:
- 503 then 200 → returns reply; `on_retry` called once with `(1, 3)`.
- 503 on all 4 attempts → `BrainError` containing "503"; 4 requests made.
- 429 → one request, quota message.
- `Retry-After: 30` → wait capped at 10 s.
- `cancelled()` true during wait → raises, no further request.
- Existing "error does not echo key" test still passes.

Manual check before claiming done: launch the app, screenshot the full window and a
380 px wide window, confirm Thai renders correctly; send one real message if the key works.

## 7. Files touched

| File | Change |
|---|---|
| `theme.py` | New: color, font, radius tokens |
| `app.py` | UI construction rewritten with CustomTkinter; action/voice/screen/Discord logic unchanged except status pill, retry event, responsive handler, bubble transcript |
| `brain.py` | Retry/cancel in `_post`; keyword pass-through |
| `thai.py` | New Thai strings |
| `Start Jarvis.cmd` | Auto-install customtkinter |
| `README.md` | Requirements, labels, busy note |
| `tests/test_ui.py`, `tests/test_boundaries.py` | Updated and new tests |

## Risks

- **Thai rendering in CustomTkinter**: CTk uses Tk font rendering like today, so Thai
  shaping should be unchanged. Verified in the manual check.
- **Many bubble widgets slow scrolling**: mitigated by the 200-row cap.
- **Retries lengthen the wait** to about 14 s before a final error. The retry card keeps
  the user informed; Stop cancels immediately.
- **First launch needs internet** for pip install; the launcher prints the manual command
  if it fails.
