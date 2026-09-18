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


class MentorModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = JarvisApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.app.study = None  # never touch the real D:\Jarvis\Study vault in tests

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_the_ladder_is_clamped_before_anything_is_shown(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.set_rung(problem, 1)
        a.memory.add_attempt(problem, "แนวคิด: ลองทุกกรณี")   # no verdict

        reply = mentor.MentorReply("เฉลยเต็ม ๆ", 5,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("ขอโค้ดเลย")

        self.assertEqual(a.memory.problem("knapsack-th")["rung"], 2)
        self.assertIn("[ขั้น 2/5", a.bubbles[-1][1].cget("text"))

    def test_the_override_records_a_give_up_and_opens_the_last_rung(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("นี่คือเฉลย", 5,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("เปิดเฉลย")

        row = a.memory.problem("knapsack-th")
        self.assertEqual(row["status"], "given-up")
        self.assertEqual(row["rung"], 5)

    def test_failure_tags_are_stored_and_reach_the_profile(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("state ผิด", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"},
                                   [{"tag": "wrong-state", "note": None}], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("ลองแล้วไม่ผ่าน")

        self.assertEqual(a.memory.profile("dp"), [("wrong-state", 1)])

    def test_a_mentor_turn_never_produces_a_pc_proposal(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("เปิด spotify ให้หน่อย")
        self.assertEqual(a.proposals, [])

    def test_a_model_error_is_shown_and_does_not_break_the_window(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        with patch("app.ask_mentor", side_effect=mentor.MentorError("คำตอบว่าง")):
            a.mentor_turn("ข้อนี้ทำไงดี")
        self.assertIn("คำตอบว่าง", a.bubbles[-1][1].cget("text"))

    def test_mentor_mode_survives_a_restart(self):
        a = self.app
        a.mentor_mode = True
        a.store.save_settings(a.model, mentor=True)
        a.close()
        self.app = JarvisApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.assertTrue(self.app.mentor_mode)

    def test_the_current_message_reaches_the_model(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply) as fake_ask:
            a.mentor_turn("มีโจทย์ knapsack ต้องช่วยด้วย")
        sent = fake_ask.call_args.args[1]
        self.assertIn("มีโจทย์ knapsack ต้องช่วยด้วย", sent)

    def test_a_cross_slug_reply_cannot_exceed_the_new_problems_gates(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        old = a.memory.upsert_problem("old-th", "Old", topic="dp")
        a.memory.set_rung(old, 3)
        a.memory.add_attempt(old, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("นี่คือโจทย์ใหม่ เฉลยเลย", 5,
                                   {"slug": "new-th", "title": "New",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("เปลี่ยนโจทย์ ข้อนี้เลย")

        self.assertEqual(a.memory.problem("new-th")["rung"], 0)
        self.assertEqual(a.memory.problem("old-th")["rung"], 3)
        self.assertIn("[ขั้น 0/5", a.bubbles[-1][1].cget("text"))

    def test_a_no_slug_override_records_a_give_up_on_the_current_problem(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("นี่คือเฉลย", 5, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("เปิดเฉลย")

        row = a.memory.problem("knapsack-th")
        self.assertEqual(row["status"], "given-up")
        self.assertEqual(row["rung"], 5)

    def test_a_given_up_problem_stays_given_up_when_the_model_says_working(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.set_rung(problem, 5)
        a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp", status="given-up")

        reply = mentor.MentorReply("ลองดูใหม่นะ", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("ลองใหม่อีกครั้ง")

        self.assertEqual(a.memory.problem("knapsack-th")["status"], "given-up")

    def test_an_attempt_with_a_typed_verdict_is_recorded(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "แนวคิด: ลองทุกกรณี")  # no verdict yet

        reply = mentor.MentorReply("โอเค ลองดูจุดนี้", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("ส่งไปได้ WA ครับ")

        attempts = a.memory.attempts(problem)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[-1]["verdict"], "WA")

    def test_a_turn_with_no_problem_has_no_rung_prefix(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("สวัสดีครับ")
        self.assertEqual(a.bubbles[-1][1].cget("text"), "ลองอ่านโจทย์อีกที")

    def test_a_memory_error_during_recording_still_shows_the_reply(self):
        import mentor
        from memory import MemoryError as MemErr
        a = self.app
        a.mentor_mode = True
        a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        reply = mentor.MentorReply("นี่คือคำตอบ", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply), \
             patch.object(a.memory, "set_rung", side_effect=MemErr("บันทึกไม่ได้")):
            a.mentor_turn("ลองดูอีกที")
        kinds = [kind for _row, _text, kind in a.bubbles]
        self.assertIn("ERROR", kinds)
        self.assertIn("นี่คือคำตอบ", a.bubbles[-1][1].cget("text"))

    def test_offer_note_warns_when_the_page_already_exists(self):
        import mentor
        a = self.app
        a.study = Mock()
        a.study.page.return_value = "---\nname: dp-intro\n---\n\nold content\n"
        a.study.render.return_value = "---\nname: dp-intro\n---\n\nnew content\n"
        note = {"slug": "dp-intro", "type": "concept", "tags": ["dp"], "lang": "th",
                "body": "new content"}
        with patch("app.messagebox.askyesno", return_value=False) as fake_ask:
            a.offer_note(note)
        message = fake_ask.call_args.args[1]
        self.assertIn("This page already exists and will be replaced.", message)


if __name__ == "__main__":
    unittest.main()
