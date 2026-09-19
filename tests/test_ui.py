"""Desktop integration tests: real CustomTkinter widgets, mocked AI and PC side effects."""
import threading
import time
import tkinter as tk
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import app
from app import MAX_ROWS, VictorApp
from brain import Reply
from local_store import LocalStore
from thai import tr


class DesktopFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
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
        a.input.insert("1.0", "สวัสดี Victor")
        a.toggle_compact()
        self.assertTrue(a.compact)
        self.assertEqual(a.sidebar.winfo_manager(), "")
        self.assertTrue(a.attributes("-topmost"))
        self.assertEqual(a.input.get("1.0", "end-1c"), "สวัสดี Victor")
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
        self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
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
        started = VictorApp(store=LocalStore(Path(self.temp.name)))
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
        # An empty bank isolates these tests from the daily serve, keeping "no current problem" reachable.
        with patch("app.bank.load", return_value=[]):
            self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.app.study = None  # never touch the real D:\Jarvis\Study vault in tests

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def turn(self, prompt):
        """Run one mentor turn to completion: worker, then the Tk-side poll."""
        worker = self.app.mentor_turn(prompt)
        if worker:
            worker.join(5)
        self.app.poll()

    def test_the_model_call_runs_off_the_ui_thread(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        release, seen = threading.Event(), []
        def fake_ask(model, text, cancelled=None):
            seen.append(threading.current_thread())
            release.wait(5)
            return mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", side_effect=fake_ask):
            worker = a.submit("ข้อนี้ทำไงดี")
            # submit returned while the model is still "thinking".
            self.assertTrue(a.busy)
            self.assertEqual(a.send_button.cget("state"), "disabled")
            before = len(a.bubbles)
            a.poll()
            self.assertEqual(len(a.bubbles), before)  # no reply yet
            release.set()
            worker.join(5)
            a.poll()
        self.assertEqual(len(seen), 1)
        self.assertIsNot(seen[0], threading.current_thread())
        self.assertFalse(a.busy)
        self.assertEqual(a.send_button.cget("state"), "normal")
        self.assertIn("ลองอ่านโจทย์อีกที", a.bubbles[-1][1].cget("text"))

    def test_stop_during_a_mentor_turn_drops_the_reply_and_records_nothing(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")  # would earn rung 1
        reply = mentor.MentorReply("ลองคิดแบบ DP", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        cancels = []
        def fake_ask(model, text, cancelled=None):
            cancels.append(cancelled)
            return reply
        with patch("app.ask_mentor", side_effect=fake_ask):
            a.submit("ใบ้หน่อย").join(5)
            self.assertFalse(a.events.empty())
            a.stop()  # reply is queued but not yet polled
            a.poll()
        self.assertTrue(cancels[0]())  # the worker's cancel flag now reads True
        self.assertEqual(a.memory.problem("knapsack-th")["rung"], 0)
        texts = "\n".join(text.cget("text") for _row, text, _kind in a.bubbles)
        self.assertNotIn("ลองคิดแบบ DP", texts)
        self.assertFalse(a.busy)
        self.assertEqual(a.send_button.cget("state"), "normal")
        self.assertIn("ใบ้หน่อย", [t["text"] for t in a.history])  # user turn kept

    def test_a_stopped_turn_cannot_land_on_the_next_one(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")  # earns rung 1
        release, calls = threading.Event(), []
        def fake_ask(model, text, cancelled=None):
            calls.append(text)
            if len(calls) == 1:  # turn A; B's prompt also quotes A via history
                release.wait(5)
                return mentor.MentorReply("คำตอบ A", 1, {"slug": "knapsack-th", "title": "Knapsack",
                                                         "topic": "dp", "status": "working"}, [], None)
            return mentor.MentorReply("คำตอบ B", 0, None, [], None)
        with patch("app.ask_mentor", side_effect=fake_ask):
            first = a.submit("คำถาม A")
            a.stop()
            second = a.submit("คำถาม B")
            second.join(5)
            release.set()
            first.join(5)
            a.poll()
        texts = "\n".join(text.cget("text") for _row, text, _kind in a.bubbles)
        self.assertIn("คำตอบ B", texts)
        self.assertNotIn("คำตอบ A", texts)
        self.assertEqual(a.memory.problem("knapsack-th")["rung"], 0)
        self.assertFalse(a.busy)
        self.assertEqual(a.send_button.cget("state"), "normal")

    def test_a_read_error_before_the_call_restores_the_window(self):
        import sqlite3
        a = self.app
        a.mentor_mode = True
        with patch("app.ask_mentor") as fake_ask, \
             patch.object(a.memory, "current_problem", side_effect=sqlite3.Error("อ่านไม่ได้")):
            self.assertIsNone(a.submit("ข้อนี้ทำไงดี"))
            a.poll()
        fake_ask.assert_not_called()
        self.assertEqual(a.bubbles[-1][2], "ERROR")
        self.assertIn("อ่านไม่ได้", a.bubbles[-1][1].cget("text"))
        self.assertFalse(a.busy)
        self.assertEqual(a.send_button.cget("state"), "normal")
        self.assertEqual(a.pill.cget("text"), app.PILL["ready"][0])

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
            self.turn("ขอโค้ดเลย")

        self.assertEqual(a.memory.problem("knapsack-th")["rung"], 2)
        shown = a.bubbles[-1][1].cget("text")
        self.assertIn("[ขั้น 2/5", shown)
        # The model proposed rung 5 but was only granted 2 — the over-rung text
        # itself must never reach the screen or the conversation history.
        self.assertNotIn("เฉลยเต็ม ๆ", shown)
        self.assertIn(mentor.WITHHELD, shown)
        self.assertNotIn("เฉลยเต็ม ๆ", "\n".join(t["text"] for t in a.history))

    def test_an_over_rung_reply_on_the_same_problem_is_withheld(self):
        """Same-problem case: the reply names the problem already in play, but
        proposes a rung it hasn't earned yet (no attempt on record)."""
        import mentor
        a = self.app
        a.mentor_mode = True
        a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")

        reply = mentor.MentorReply("ใช้เทคนิค DP", 3,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            self.turn("บอกเทคนิคหน่อย")

        self.assertEqual(a.memory.problem("knapsack-th")["rung"], 0)
        shown = a.bubbles[-1][1].cget("text")
        self.assertIn("[ขั้น 0/5", shown)
        self.assertIn(mentor.WITHHELD, shown)
        self.assertNotIn("ใช้เทคนิค DP", shown)

    def test_an_over_rung_reply_with_no_problem_is_withheld_without_a_prefix(self):
        """No current problem and the model names none either: target_id stays
        None, so the withhold check must fall back to the pre-call ceiling
        instead of trusting an unrecorded rung."""
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("นี่คือเฉลยเต็ม ๆ", 5, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            self.turn("ขอเฉลยเลย")

        shown = a.bubbles[-1][1].cget("text")
        self.assertNotIn("นี่คือเฉลยเต็ม ๆ", shown)
        self.assertEqual(shown, mentor.WITHHELD)  # no problem → no rung prefix
        self.assertNotIn("นี่คือเฉลยเต็ม ๆ", "\n".join(t["text"] for t in a.history))

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
            self.turn("เปิดเฉลย")

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
            self.turn("ลองแล้วไม่ผ่าน")

        self.assertEqual(a.memory.profile("dp"), [("wrong-state", 1)])

    def test_a_mentor_turn_never_produces_a_pc_proposal(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            self.turn("เปิด spotify ให้หน่อย")
        self.assertEqual(a.proposals, [])

    def test_a_model_error_is_shown_and_does_not_break_the_window(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        with patch("app.ask_mentor", side_effect=mentor.MentorError("คำตอบว่าง")):
            self.turn("ข้อนี้ทำไงดี")
        self.assertIn("คำตอบว่าง", a.bubbles[-1][1].cget("text"))

    def test_mentor_mode_survives_a_restart(self):
        a = self.app
        a.mentor_mode = True
        a.store.save_settings(a.model, mentor=True)
        a.close()
        self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.assertTrue(self.app.mentor_mode)

    def test_the_current_message_reaches_the_model(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply) as fake_ask:
            self.turn("มีโจทย์ knapsack ต้องช่วยด้วย")
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
            self.turn("เปลี่ยนโจทย์ ข้อนี้เลย")

        self.assertEqual(a.memory.problem("new-th")["rung"], 0)
        self.assertEqual(a.memory.problem("old-th")["rung"], 3)
        shown = a.bubbles[-1][1].cget("text")
        self.assertIn("[ขั้น 0/5", shown)
        # Moving to a new problem must never leak a rung-5 solution under a
        # rung-0 label.
        self.assertNotIn("นี่คือโจทย์ใหม่ เฉลยเลย", shown)
        self.assertIn(mentor.WITHHELD, shown)
        self.assertNotIn("นี่คือโจทย์ใหม่ เฉลยเลย", "\n".join(t["text"] for t in a.history))

    def test_a_no_slug_override_records_a_give_up_on_the_current_problem(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("นี่คือเฉลย", 5, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            self.turn("เปิดเฉลย")

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
            self.turn("ลองใหม่อีกครั้ง")

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
            self.turn("ส่งไปได้ WA ครับ")

        attempts = a.memory.attempts(problem)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[-1]["verdict"], "WA")

    def test_an_attempt_on_a_brand_new_problem_is_recorded(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("เข้าใจแล้ว มาดูกัน", 0,
                                   {"slug": "new-th", "title": "New",
                                    "topic": "dp", "status": "working"},
                                   [], None, attempt=True)
        with patch("app.ask_mentor", return_value=reply):
            self.turn("นี่คือโค้ดของผม ได้ WA")

        row = a.memory.problem("new-th")
        attempts = a.memory.attempts(row["id"])
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["verdict"], "WA")
        self.assertEqual(row["rung"], 0)

    def test_a_turn_with_no_problem_has_no_rung_prefix(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            self.turn("สวัสดีครับ")
        self.assertEqual(a.bubbles[-1][1].cget("text"), "ลองอ่านโจทย์อีกที")

    def test_a_memory_error_during_recording_still_shows_a_reply(self):
        import mentor
        from memory import MemoryError as MemErr
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")  # earns rung 1
        reply = mentor.MentorReply("นี่คือคำตอบ", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply), \
             patch.object(a.memory, "set_rung", side_effect=MemErr("บันทึกไม่ได้")):
            self.turn("ลองดูอีกที")
        kinds = [kind for _row, _text, kind in a.bubbles]
        self.assertIn("ERROR", kinds)
        # The rung was earned (attempt with a verdict on record), so this is an
        # honest reply, not an over-rung one — the DB failure alone must not
        # withhold text the user was entitled to.
        self.assertIn("นี่คือคำตอบ", a.bubbles[-1][1].cget("text"))

    def test_offer_note_warns_when_the_page_already_exists(self):
        a = self.app
        a.study = Mock()
        a.study.wiki = Path(self.temp.name)
        (a.study.wiki / "dp-intro.md").write_text("old content", encoding="utf-8")
        a.study.render.return_value = "---\nname: dp-intro\n---\n\nnew content\n"
        note = {"slug": "dp-intro", "type": "concept", "tags": ["dp"], "lang": "th",
                "body": "new content"}
        with patch("app.messagebox.askyesno", return_value=False) as fake_ask:
            a.offer_note(note)
        message = fake_ask.call_args.args[1]
        self.assertIn(tr("This page already exists and will be replaced."), message)


class DailyCardTests(unittest.TestCase):
    def setUp(self):
        from bank import Entry
        self.temp = tempfile.TemporaryDirectory()
        self.entries = [Entry(id=f"camp1/p{n}", slug=f"p{n}", title=f"P{n}", level=1,
                              topic="implementation", time_limit=1.0, statement="# P\n",
                              tests=(("1\n", "1\n"),)) for n in range(4)]
        with patch("app.bank.load", return_value=self.entries):
            self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.app.study = None

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def today_rows(self):
        from datetime import date
        return {r["role"]: r for r in self.app.memory.daily_rows(date.today().isoformat())}

    def grade(self, role, result):
        with patch("app.grader.grade", return_value=result):
            worker = self.app.start_grade(role)
            worker.join(5)
            self.app.poll()

    def test_daily_folders_live_under_the_test_store_not_the_real_vault(self):
        from datetime import date
        self.assertTrue(str(self.app.daily_root).startswith(self.temp.name))
        self.assertTrue((self.app.daily_root / date.today().isoformat() / "main" / "sol.cpp").exists())

    def test_today_card_lists_both_problems(self):
        import customtkinter as ctk
        texts = " ".join(w.cget("text") for w in self.app.today_card.winfo_children()
                         if isinstance(w, ctk.CTkLabel))
        self.assertIn("main", texts)
        self.assertIn("warmup", texts)

    def test_accepted_solution_is_recorded_and_solves_the_problem(self):
        import grader
        self.grade("main", grader.Result("AC", 1, 1, "AC 1/1"))
        rows = self.today_rows()
        self.assertTrue(rows["main"]["ac"])
        self.assertEqual(rows["main"]["status"], "solved")
        self.assertTrue(any("AC 1/1" in b[1].cget("text") for b in self.app.bubbles))
        self.assertFalse(self.app.busy)

    def test_wrong_answer_is_recorded_without_solving(self):
        import grader
        self.grade("warmup", grader.Result("WA", 0, 1, "WA on test 1/1"))
        rows = self.today_rows()
        self.assertTrue(rows["warmup"]["graded"])
        self.assertFalse(rows["warmup"]["ac"])
        self.assertEqual(rows["warmup"]["status"], "working")

    def test_archive_ac_is_only_a_sample_check(self):
        import grader
        from bank import Entry
        row = self.today_rows()["main"]
        self.app.bank_by_id[row["source"]] = Entry(
            id=row["source"], slug=row["slug"], title=row["title"], level=3, topic="dp",
            time_limit=1.0, statement="#", tests=(("1\n", "1\n"),), url="https://example.org/p")
        self.grade("main", grader.Result("AC", 1, 1, "AC 1/1"))
        self.assertEqual(self.app.memory.attempts(row["problem_id"])[-1]["verdict"], "unsubmitted")
        self.assertTrue(any("https://example.org/p" in b[1].cget("text") for b in self.app.bubbles))

    def test_typing_the_grade_word_in_mentor_mode_grades_instead_of_asking(self):
        import grader
        self.app.mentor_mode = True
        with patch("app.ask_mentor") as ask, \
                patch("app.grader.grade", return_value=grader.Result("AC", 1, 1, "AC 1/1")):
            worker = self.app.submit("ตรวจ")
            worker.join(5)
            self.app.poll()
        ask.assert_not_called()
        self.assertTrue(self.today_rows()["main"]["ac"])

    def test_a_general_mentor_message_attaches_to_todays_main_problem(self):
        """Spec 6 step 5: with a populated bank, a general mentor message (no
        verdict, no ตรวจ) attaches to today's main problem, not a blank slate."""
        import mentor
        self.app.mentor_mode = True
        main_id = self.today_rows()["main"]["problem_id"]
        reply = mentor.MentorReply("ลองเล่าว่าอ่านโจทย์ว่าอย่างไร", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            worker = self.app.mentor_turn("สวัสดีครับ")
            worker.join(5)
            self.app.poll()
        shown = self.app.bubbles[-1][1].cget("text")
        self.assertIn(mentor.label(0), shown)
        current = self.app.memory.current_problem()
        self.assertIsNotNone(current)
        self.assertEqual(current["id"], main_id)

    def test_stop_during_grading_records_nothing(self):
        import grader
        release = threading.Event()
        def slow(*args, **kwargs):
            release.wait(5)
            return grader.Result("AC", 1, 1, "AC 1/1")
        with patch("app.grader.grade", side_effect=slow):
            worker = self.app.start_grade("main")
            self.app.stop()
            release.set()
            worker.join(5)
            self.app.poll()
        for r in self.today_rows().values():
            self.assertFalse(r["graded"])


if __name__ == "__main__":
    unittest.main()
