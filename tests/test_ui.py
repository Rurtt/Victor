"""Desktop integration tests: real CustomTkinter widgets, mocked AI and PC side effects."""
import time
import tkinter as tk
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import app
from app import MAX_ROWS, JarvisApp
from brain import Reply
from local_store import LocalStore


class DesktopFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = JarvisApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_chat_proposal_stop_and_late_response(self):
        a = self.app
        a.key = "test-key"
        # Deliberately an action outside AUTO_RUN: this test is about the approval flow.
        proposal = {"name": "control_screen", "arguments": {"goal": "จัดเรียงหน้าต่าง"}}
        runner = Mock()
        a.gate.runner = runner
        with patch("app.ask", return_value=Reply("I can do that on screen for you.", [proposal])) as fake_ask:
            a.input.insert("1.0", "Tidy my windows")
            a.send()
            deadline = time.monotonic() + 2
            while a.busy and time.monotonic() < deadline:
                a.update()
                time.sleep(0.01)
        self.assertFalse(a.busy)
        self.assertIn("cancelled", fake_ask.call_args.kwargs)
        self.assertIn("on_retry", fake_ask.call_args.kwargs)
        self.assertEqual(len(a.proposals), 1)
        self.assertIn("รออนุญาต", a.pending_label.cget("text"))
        runner.assert_not_called()
        generation = a.generation
        a.stop()
        self.assertEqual(a.gate.pending, {})
        a.events.put(("reply", generation, (Reply("late", [proposal]), "old", False)))
        a.poll()
        self.assertFalse(a.proposals)
        runner.assert_not_called()

    def test_dialogs_construct_and_close(self):
        a = self.app
        for opener in (a.settings, a.summary_window, a.actions_window, a.discord_window):
            opener()
            a.update_idletasks()
            dialogs = [w for w in a.winfo_children() if isinstance(w, tk.Toplevel)]
            self.assertEqual(len(dialogs), 1)
            dialogs[0].destroy()

    def test_exact_preview_and_button_approval(self):
        a = self.app
        payload = {"name": "save_note", "arguments": {"text": "My complete note\nwith another line."}}
        runner = Mock(return_value="Note saved.")
        a.gate.runner = runner
        a.proposals.append((a.gate.propose(payload), payload))
        def approve():
            dialog = next(w for w in a.winfo_children() if isinstance(w, tk.Toplevel))
            self.assertIn(payload["arguments"]["text"], dialog.preview.get("1.0", "end"))
            self.assertEqual(dialog.approve_button.cget("text"), "อนุญาตให้ทำรายการนี้")
            dialog.approve_button.invoke()
        a.after(50, approve)
        a.review_actions()
        runner.assert_called_once_with(payload)
        self.assertFalse(a.gate.pending)

    def test_discord_auto_send_only_for_listed_targets(self):
        a = self.app
        runner = Mock(return_value="sent")
        a.gate.runner = runner
        a.discord = {"auto": True, "targets": {"friend": "https://discord.com/channels/@me/1"}}
        listed = {"name": "discord_send", "arguments": {"target": "friend", "text": "hi"}}
        other = {"name": "discord_send", "arguments": {"target": "boss", "text": "hi"}}
        a.busy = True
        a.events.put(("reply", a.generation, (Reply("ok", [listed, other]), "p", False)))
        a.poll()
        runner.assert_called_once_with(listed)
        self.assertEqual([p[1] for p in a.proposals], [other])

    def test_stop_cancels_screen_task(self):
        a = self.app
        a.start_screen_task("open spotify")
        generation = a.generation
        a.stop()
        self.assertIsNone(a.screen_goal)
        with patch("app.screen.capture") as capture:
            a.screen_capture()
        capture.assert_not_called()
        a.events.put(("screen", generation, ("late", {"kind": "click", "x": 1, "y": 1, "label": ""}, None)))
        a.poll()  # stale generation: no dialog, no click

    def test_compact_mode_keeps_chat_and_restores_sidebar(self):
        a = self.app
        a.input.insert("1.0", "สวัสดี Jarvis")
        a.toggle_compact()
        self.assertTrue(a.compact)
        self.assertEqual(a.sidebar.winfo_manager(), "")
        self.assertTrue(a.attributes("-topmost"))
        self.assertEqual(a.input.get("1.0", "end-1c"), "สวัสดี Jarvis")
        a.toggle_compact()
        self.assertFalse(a.compact)
        self.assertEqual(a.sidebar.winfo_manager(), "pack")
        self.assertFalse(a.attributes("-topmost"))

    def test_narrow_width_hides_sidebar_and_shows_menu(self):
        a = self.app
        a.apply_layout(600)
        self.assertTrue(a.narrow)
        self.assertEqual(a.sidebar.winfo_manager(), "")
        self.assertEqual(a.voice_row.winfo_manager(), "")
        self.assertEqual(a.menu_button.winfo_manager(), "pack")
        self.assertEqual(a.pill.winfo_manager(), "pack")
        a.apply_layout(400)
        self.assertEqual(a.pill.winfo_manager(), "")
        a.apply_layout(1000)
        self.assertFalse(a.narrow)
        self.assertEqual(a.sidebar.winfo_manager(), "pack")
        self.assertEqual(a.voice_row.winfo_manager(), "pack")
        self.assertEqual(a.menu_button.winfo_manager(), "")
        self.assertEqual(a.pill.winfo_manager(), "pack")

    def test_menu_offers_every_sidebar_action(self):
        menu = self.app.build_menu()
        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) != "separator"]
        for text in ("แชตใหม่", "สรุปข้อความ / ไฟล์", "ควบคุมคอมพิวเตอร์", "Discord และกฎการส่ง",
                     "ตั้งค่า AI และ API key", "อ่านคำตอบ", "อ่านตอบอัตโนมัติ", "เปิดโฟลเดอร์โปรแกรม"):
            self.assertIn(text, labels)
        menu.destroy()

    def test_retry_notice_only_for_current_request(self):
        a = self.app
        a.busy = True
        rows = len(a.bubbles)
        a.events.put(("retry", a.generation - 1, (1, 3)))
        a.poll()
        self.assertEqual(len(a.bubbles), rows)
        a.events.put(("retry", a.generation, (2, 3)))
        a.poll()
        self.assertEqual(len(a.bubbles), rows + 1)
        self.assertEqual(a.bubbles[-1][2], "WARN")
        self.assertIn("(2/3)", a.bubbles[-1][1].cget("text"))
        self.assertTrue(a.busy)

    def test_transcript_keeps_last_rows_only(self):
        a = self.app
        for i in range(MAX_ROWS + 5):
            a.add_message("YOU", f"message {i}")
        self.assertEqual(len(a.bubbles), MAX_ROWS)
        self.assertEqual(a.bubbles[-1][1].cget("text"), f"message {MAX_ROWS + 4}")

    def test_status_pill_follows_state(self):
        a = self.app
        a.set_status("Thinking with Gemini… • Microphone off", "thinking")
        self.assertIn("กำลังคิด", a.pill.cget("text"))
        self.assertEqual(a.detail.cget("text"), "")
        a.set_status("Dictation ready — review it and press Send • Microphone off")
        self.assertIn("พร้อม", a.pill.cget("text"))
        self.assertEqual(a.detail.cget("text"), "ตรวจข้อความแล้วกดส่ง • ไมโครโฟนปิด")


class BackgroundModeTests(unittest.TestCase):
    """Tray routing and the hands-free turn the wake word starts."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = JarvisApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_tray_events_reach_the_matching_action_and_ignore_junk(self):
        a = self.app
        with patch.object(a, "show_window") as show, patch.object(a, "stop") as stop:
            a.on_tray("open")
            a.on_tray("stop")
            a.on_tray("not-a-menu-item")
        show.assert_called_once()
        stop.assert_called_once()

    def test_closing_the_window_without_a_tray_icon_really_exits(self):
        a = self.app
        self.assertIsNone(a.tray)
        with patch.object(a, "close") as close:
            a.hide_to_tray()
        close.assert_called_once()

    def test_the_wake_word_records_without_opening_the_window(self):
        a = self.app
        a.wake_enabled.set(True)
        with patch("app.voice.beep"), patch.object(a, "listen") as listen:
            a.on_wake("wake", "")
        self.assertTrue(a.hands_free)
        listen.assert_called_once_with(seconds=app.WAKE_SECONDS)

    def test_a_wake_word_heard_while_busy_is_ignored(self):
        a = self.app
        a.wake_enabled.set(True)
        a.busy = True
        with patch.object(a, "listen") as listen:
            a.on_wake("wake", "")
        listen.assert_not_called()
        self.assertFalse(a.hands_free)

    def test_a_wake_listener_failure_switches_the_wake_word_off(self):
        a = self.app
        a.wake_enabled.set(True)
        a.on_wake("error", "the microphone disappeared")
        self.assertFalse(a.wake_enabled.get())
        self.assertIn("microphone", a.bubbles[-1][1].cget("text"))

    def test_a_hands_free_transcript_is_sent_and_the_reply_is_read_aloud(self):
        a = self.app
        a.key = "test-key"
        a.hands_free = True
        with patch("app.ask", return_value=Reply("ได้เลย", [])), patch.object(a, "speak") as speak:
            a.events.put(("dictation", a.speech_generation, "เปิดเครื่องคิดเลข"))
            deadline = time.monotonic() + 3
            while not speak.called and time.monotonic() < deadline:
                a.update()
                time.sleep(0.01)
        speak.assert_called_once_with("ได้เลย")
        self.assertFalse(a.hands_free)

    def test_a_typed_dictation_is_only_inserted_for_review(self):
        a = self.app
        a.key = "test-key"
        self.assertFalse(a.hands_free)
        with patch("app.ask") as never_asked:
            a.events.put(("dictation", a.speech_generation, "สวัสดี"))
            deadline = time.monotonic() + 2
            while "สวัสดี" not in a.input.get("1.0", "end-1c") and time.monotonic() < deadline:
                a.update()
                time.sleep(0.01)
        never_asked.assert_not_called()
        self.assertIn("สวัสดี", a.input.get("1.0", "end-1c"))


class PersistentHistoryTests(unittest.TestCase):
    """History used to live only in RAM. Restarting the app must not erase it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def start(self):
        started = JarvisApp(store=LocalStore(Path(self.temp.name)))
        started.withdraw()
        return started

    def answer(self, a, prompt, text):
        a.events.put(("reply", a.generation, (Reply(text, []), prompt, False)))
        a.poll()

    def test_history_survives_a_restart(self):
        a = self.start()
        self.answer(a, "จำเลขนี้ไว้ 42", "จำแล้วครับ")
        self.assertEqual(len(a.history), 2)
        a.close()

        revived = self.start()
        try:
            self.assertEqual([t["text"] for t in revived.history],
                             ["จำเลขนี้ไว้ 42", "จำแล้วครับ"])
        finally:
            revived.close()

    def test_new_chat_is_not_undone_by_a_restart(self):
        a = self.start()
        self.answer(a, "เรื่องเก่า", "รับทราบ")
        a.new_chat()
        self.assertEqual(a.history, [])
        a.close()

        revived = self.start()
        try:
            self.assertEqual(revived.history, [])
        finally:
            revived.close()


if __name__ == "__main__":
    unittest.main()
