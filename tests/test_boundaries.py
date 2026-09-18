import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib import error

from actions import ActionGate, PolicyError, WindowsActions, validate
from brain import BrainError, NoRedirect, ask, decode_reply
from documents import read_document


def action(name="open_app", **args):
    return {"name": name, "arguments": args or {"app": "calculator"}}


def response(actions=None, text="Here is the result.", finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [
        {"text": json.dumps({"reply": text, "actions": actions or []})}
    ]}}]}


class CapabilityTests(unittest.TestCase):
    def test_model_cannot_self_approve_or_supply_commands(self):
        malicious = [action("run_shell", command="whoami"), action(app="powershell"),
                     action(app="notepad & calc"), action(app="calculator", confirmed="yes"),
                     {**action(), "approved": True}, action("open_folder", folder="../../"),
                     action("save_note", text="hi", path="C:/outside.txt")]
        for payload in malicious:
            with self.subTest(payload=payload), self.assertRaises(PolicyError):
                validate(payload)

    def test_no_action_runs_until_local_approval(self):
        runner = Mock(return_value="done")
        gate = ActionGate(runner)
        ticket = gate.propose(action())
        runner.assert_not_called()
        with self.assertRaises(PolicyError):
            gate.approve("yes")
        self.assertEqual(gate.approve(ticket), "done")
        runner.assert_called_once_with(action())
        with self.assertRaises(PolicyError):
            gate.approve(ticket)

    def test_cancel_and_stop_revoke_tickets(self):
        runner = Mock()
        gate = ActionGate(runner)
        one, two = gate.propose(action()), gate.propose(action())
        gate.reject(one)
        gate.clear()
        for ticket in (one, two):
            with self.assertRaises(PolicyError):
                gate.approve(ticket)
        runner.assert_not_called()

    def test_proposed_arguments_cannot_be_changed_after_preview(self):
        runner = Mock()
        gate = ActionGate(runner)
        payload = action()
        ticket = gate.propose(payload)
        payload["arguments"]["app"] = "powershell"
        gate.approve(ticket)
        runner.assert_called_once_with(action())

    def test_url_policy_blocks_local_files_protocols_and_credentials(self):
        urls = ["file:///C:/test.exe", "javascript:alert(1)", "http://example.com", "https://localhost",
                "https://127.0.0.1", "https://127.1", "https://[::1]", "https://a.local", "https://a.lan",
                "https://user:pass@example.com", "https://example.com:8000", "https://example.com\n",
                "https://example.com\\@localhost", "https://x.com:bad"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(PolicyError):
                validate(action("open_website", url=url))
        self.assertEqual(validate(action("open_website", url="https://example.com/a?q=test"))["name"], "open_website")

    def test_notes_are_new_text_files_and_never_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            run = WindowsActions(Path(d))
            run(action("save_note", text="first"))
            run(action("save_note", text="second"))
            files = list((Path(d) / "notes").glob("*.txt"))
            self.assertEqual(len(files), 2)
            self.assertEqual({f.read_text() for f in files}, {"first", "second"})

    def test_executable_is_fixed_and_shell_disabled(self):
        with patch("actions.subprocess.Popen") as process:
            WindowsActions(Path.cwd())(action())
        args, kwargs = process.call_args
        self.assertEqual(Path(args[0][0]).name, "calc.exe")
        self.assertFalse(kwargs["shell"])
        self.assertEqual(len(args[0]), 1)

    def test_notes_reject_redirected_directory(self):
        with tempfile.TemporaryDirectory() as d, patch("actions.Path.is_junction", return_value=True):
            with self.assertRaises(PolicyError):
                WindowsActions(Path(d))(action("save_note", text="private note"))
            self.assertFalse(list(Path(d).rglob("*.txt")))


class BrainTests(unittest.TestCase):
    def test_summary_cannot_emit_actions_even_if_document_instructs_it(self):
        with self.assertRaises(BrainError):
            decode_reply(response([action()]), allow_actions=False)

    def test_invalid_or_truncated_model_output_fails_closed(self):
        payloads = [{}, response([action("run_shell", command="cmd")]), response(finish="MAX_TOKENS"),
                    response([action()] * 4), response(text=123)]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(BrainError):
                decode_reply(payload)

    def test_valid_chat_response(self):
        result = decode_reply(response([action()]))
        self.assertEqual(result.actions, [action()])

    def test_transport_key_stays_in_header_and_summary_has_no_history(self):
        fake = io.BytesIO(json.dumps(response()).encode())
        with patch("brain.request.build_opener") as opener:
            opener.return_value.open.return_value = fake
            result = ask("test-key", "gemini-3.8-flash", [{"role": "user", "text": "OLD SECRET"}],
                         "My selected text", summary=True)
            req = opener.return_value.open.call_args.args[0]
        self.assertNotIn("test-key", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "test-key")
        body = json.loads(req.data)
        self.assertEqual(len(body["contents"]), 1)
        self.assertNotIn("OLD SECRET", req.data.decode())
        self.assertEqual(result.text, "Here is the result.")

    def test_error_does_not_echo_key_or_request_contents(self):
        with patch("brain.request.build_opener") as opener:
            opener.return_value.open.side_effect = error.HTTPError("url", 403, "secret-key", {}, None)
            with self.assertRaises(BrainError) as raised:
                ask("secret-key", "gemini-3.8-flash", [], "private document")
        self.assertNotIn("secret-key", str(raised.exception))

    def test_redirect_is_blocked(self):
        with self.assertRaises(BrainError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example")

    def test_key_and_model_injection_prevented_before_request(self):
        for key, model in [("key\nInjected: x", "gemini-3.8-flash"), ("key", "../other")]:
            with self.assertRaises(BrainError), patch("brain.request.build_opener") as opener:
                ask(key, model, [], "hello")
            opener.assert_not_called()


class ScreenAndDiscordTests(unittest.TestCase):
    def test_screen_steps_fail_closed(self):
        from screen import validate_step
        bad = [None, {"kind": "run_shell"}, {"kind": "click", "x": 1001, "y": 5}, {"kind": "click", "x": "5", "y": 5},
               {"kind": "click", "x": True, "y": 5}, {"kind": "type", "text": "line\nEnter"},
               {"kind": "key", "key": "win+r"}, {"kind": "scroll", "x": 1, "y": 1, "amount": 0}]
        for step in bad:
            with self.subTest(step=step), self.assertRaises(PolicyError):
                validate_step(step)
        # Extra fields from the model are dropped, not used.
        self.assertEqual(validate_step({"kind": "click", "x": 500, "y": 0, "text": "ignored", "label": "Play"}),
                         {"kind": "click", "label": "Play", "x": 500, "y": 0})
        self.assertEqual(validate_step({"kind": "type", "text": "สวัสดี"})["text"], "สวัสดี")

    def test_click_maps_normalized_coordinates_to_screenshot_pixels(self):
        import screen
        with patch("screen.ctypes.windll") as windll, patch("screen.time.sleep"):
            screen.perform({"kind": "click", "x": 1000, "y": 500, "label": "x"}, (2560, 1440))
        windll.user32.SetCursorPos.assert_called_once_with(2559, 720)

    def test_decode_screen_step(self):
        from brain import decode_step
        ok = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(
            {"reply": "กดเล่น", "step": {"kind": "click", "x": 10, "y": 20, "label": "Play"}})}]}}]}
        self.assertEqual(decode_step(ok)[1]["x"], 10)
        bad = json.loads(json.dumps(ok))
        bad["candidates"][0]["content"]["parts"][0]["text"] = json.dumps({"reply": "", "step": {"kind": "key", "key": "win+r"}})
        with self.assertRaises(BrainError):
            decode_step(bad)

    def test_discord_text_rules(self):
        for text in ["hi\nsecond line", "@everyone come", "x" * 1001]:
            with self.subTest(text=text[:20]), self.assertRaises(PolicyError):
                validate(action("discord_send", target="friend", text=text))

    def test_discord_allowlist_rate_limit_and_foreground_check(self):
        run = WindowsActions(Path.cwd())
        run.discord_targets = {"friend": "https://discord.com/channels/@me/123"}
        with patch("actions.os.startfile", create=True) as start, patch("actions.time.sleep"), \
                patch("screen.foreground_exe", return_value=r"C:\x\Discord.exe"), \
                patch("screen.type_text") as typed, patch("screen.press") as press:
            with self.assertRaises(PolicyError):
                run(action("discord_send", target="stranger", text="hi"))
            start.assert_not_called()
            run(action("discord_send", target="friend", text="สวัสดี"))
            start.assert_called_once_with("discord://-/channels/@me/123")
            typed.assert_called_once_with("สวัสดี")
            press.assert_called_once_with("enter")
            for _ in range(9):
                run(action("discord_send", target="friend", text="hi"))
            with self.assertRaises(PolicyError):
                run(action("discord_send", target="friend", text="one too many"))
        with patch("actions.os.startfile", create=True), patch("actions.time.sleep"), \
                patch("screen.foreground_exe", return_value=r"C:\x\chrome.exe"), \
                patch("screen.type_text") as typed, patch("screen.press") as press:
            run.discord_sent.clear()
            with self.assertRaises(PolicyError):
                run(action("discord_send", target="friend", text="hi"))
            typed.assert_not_called()
            press.assert_not_called()


class DocumentTests(unittest.TestCase):
    def test_text_import_and_binary_size_limits(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.txt"
            p.write_text("hello", encoding="utf-8")
            self.assertEqual(read_document(p), "hello")
            for content in (b"binary\x00", b"a" * 240001, b"\xff"):
                p.write_bytes(content)
                with self.assertRaises(ValueError):
                    read_document(p)
            with self.assertRaises(ValueError):
                read_document(Path(d) / "script.exe")


class VoiceTests(unittest.TestCase):
    def test_tts_request_and_wav_output(self):
        import base64, wave
        from brain import TTS_MODEL, synthesize
        from voice import pcm_to_wav
        pcm = b"\x01\x00" * 2400
        audio = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"inlineData": {"mimeType": "audio/L16;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]}
        with patch("brain.request.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps(audio).encode())
            self.assertEqual(synthesize("test-key", "สวัสดี"), pcm)
            req = opener.return_value.open.call_args.args[0]
        self.assertIn(TTS_MODEL, req.full_url)
        body = json.loads(req.data)
        self.assertEqual(body["generationConfig"]["responseModalities"], ["AUDIO"])
        with wave.open(io.BytesIO(pcm_to_wav(pcm))) as w:
            self.assertEqual((w.getframerate(), w.getsampwidth(), w.getnchannels(), w.getnframes()), (24000, 2, 1, 2400))

    def test_transcribe_sends_audio_and_returns_text_only(self):
        from brain import transcribe
        with patch("brain.request.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps(response()).encode())
            transcribe("test-key", "gemini-3.8-flash", b"RIFF....WAVE")
            body = json.loads(opener.return_value.open.call_args.args[0].data)
        self.assertEqual(body["contents"][0]["parts"][1]["inlineData"]["mimeType"], "audio/wav")
        self.assertNotIn("responseJsonSchema", body["generationConfig"])  # no actions possible from voice


class RetryTests(unittest.TestCase):
    def busy(self, code=503, headers=None):
        return error.HTTPError("url", code, "busy", headers or {}, None)

    def ok(self):
        return io.BytesIO(json.dumps(response()).encode())

    def test_503_then_success_retries_once_and_reports(self):
        seen = []
        with patch("brain.request.build_opener") as opener, patch("brain.time.sleep") as sleep:
            opener.return_value.open.side_effect = [self.busy(), self.ok()]
            result = ask("test-key", "gemini-3.8-flash", [], "hello",
                         on_retry=lambda n, total: seen.append((n, total)))
        self.assertEqual(result.text, "Here is the result.")
        self.assertEqual(seen, [(1, 3)])
        self.assertEqual(opener.return_value.open.call_count, 2)
        self.assertEqual(sleep.call_count, 20)  # 2 s in 0.1 s slices

    def test_gives_up_after_three_retries_with_thai_busy_message(self):
        with patch("brain.request.build_opener") as opener, patch("brain.time.sleep"):
            opener.return_value.open.side_effect = [self.busy() for _ in range(4)]
            with self.assertRaises(BrainError) as raised:
                ask("test-key", "gemini-3.8-flash", [], "hello")
        self.assertEqual(opener.return_value.open.call_count, 4)
        self.assertIn("503", str(raised.exception))
        self.assertIn("ไม่ว่าง", str(raised.exception))
        self.assertNotIn("test-key", str(raised.exception))

    def test_quota_429_is_not_retried(self):
        with patch("brain.request.build_opener") as opener, patch("brain.time.sleep") as sleep:
            opener.return_value.open.side_effect = self.busy(429)
            with self.assertRaises(BrainError) as raised:
                ask("test-key", "gemini-3.8-flash", [], "hello")
        self.assertEqual(opener.return_value.open.call_count, 1)
        sleep.assert_not_called()
        self.assertIn("quota", str(raised.exception))

    def test_retry_after_header_is_capped_at_ten_seconds(self):
        with patch("brain.request.build_opener") as opener, patch("brain.time.sleep") as sleep:
            opener.return_value.open.side_effect = [self.busy(503, {"Retry-After": "30"}), self.ok()]
            ask("test-key", "gemini-3.8-flash", [], "hello")
        self.assertEqual(sleep.call_count, 100)  # 10 s cap in 0.1 s slices

    def test_stop_during_wait_cancels_without_new_request(self):
        checks = {"n": 0}
        def cancelled():
            checks["n"] += 1
            return checks["n"] > 3
        with patch("brain.request.build_opener") as opener, patch("brain.time.sleep"):
            opener.return_value.open.side_effect = [self.busy(), self.ok()]
            with self.assertRaises(BrainError):
                ask("test-key", "gemini-3.8-flash", [], "hello", cancelled=cancelled)
        self.assertEqual(opener.return_value.open.call_count, 1)

    def test_voice_calls_accept_retry_callbacks(self):
        from brain import transcribe
        with patch("brain.request.build_opener") as opener, patch("brain.time.sleep"):
            opener.return_value.open.side_effect = [self.busy(502), self.ok()]
            transcribe("test-key", "gemini-3.8-flash", b"RIFF....WAVE", on_retry=lambda n, t: None,
                       cancelled=lambda: False)
        self.assertEqual(opener.return_value.open.call_count, 2)


if __name__ == "__main__":
    unittest.main()
