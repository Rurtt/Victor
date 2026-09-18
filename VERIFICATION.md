# Verification — 2026-09-16

## Passed

- 76 automated tests (`python -m unittest discover -s tests`) across the policy
  layer, cloud request handling, speech cancellation, provider routing, the tray
  message loop, the wake-word turn, and real Tk desktop flows with simulated AI
  results.
- `python app.py` starts clean with no stderr output.
- Measured idle cost on this PC: 0.55 % of one core and 59 MB resident, against
  2.73 % and 60 MB for the previous build over the same 20-second idle window.
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
