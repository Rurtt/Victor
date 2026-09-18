from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import mentor
from memory import Memory


class LadderTests(unittest.TestCase):
    def test_the_model_cannot_promote_itself_more_than_one_rung(self):
        self.assertEqual(
            mentor.allowed_rung(1, 5, has_attempt=True, has_verdict=True), 2)

    def test_rung_one_needs_an_attempt(self):
        self.assertEqual(
            mentor.allowed_rung(0, 1, has_attempt=False, has_verdict=False), 0)
        self.assertEqual(
            mentor.allowed_rung(0, 1, has_attempt=True, has_verdict=False), 1)

    def test_rung_four_needs_a_verdict(self):
        self.assertEqual(
            mentor.allowed_rung(3, 4, has_attempt=True, has_verdict=False), 3)
        self.assertEqual(
            mentor.allowed_rung(3, 4, has_attempt=True, has_verdict=True), 4)

    def test_an_unlock_already_earned_is_never_taken_away(self):
        self.assertEqual(
            mentor.allowed_rung(3, 1, has_attempt=True, has_verdict=True), 3)

    def test_label_names_the_rung_in_thai(self):
        self.assertEqual(mentor.label(3), "[ขั้น 3/5: เทคนิค]")
        self.assertEqual(mentor.label(0), "[ขั้น 0/5: อ่านโจทย์]")

    def test_the_override_phrase_is_recognised_anywhere_in_the_line(self):
        self.assertTrue(mentor.is_override("เปิดเฉลย"))
        self.assertTrue(mentor.is_override("  ยอมแล้ว เปิดเฉลย ให้หน่อย  "))
        self.assertFalse(mentor.is_override("อย่าเพิ่งเปิดนะ"))


class MemoryQueryTests(unittest.TestCase):
    def test_attempts_and_current_problem(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory(Path(d))
            try:
                first = memory.upsert_problem("a-th", "A", topic="dp")
                memory.add_attempt(first, "แนวคิด: ลองทุกกรณี")
                second = memory.upsert_problem("b-th", "B", topic="graph")
                memory.add_attempt(second, "int main(){}", verdict="WA")

                self.assertEqual(len(memory.attempts(first)), 1)
                self.assertIsNone(memory.attempts(first)[0]["verdict"])
                self.assertEqual(memory.attempts(second)[0]["verdict"], "WA")
                # Most recently updated problem that is still being worked on.
                self.assertEqual(memory.current_problem()["slug"], "b-th")
            finally:
                memory.close()

    def test_current_problem_ignores_finished_work(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory(Path(d))
            try:
                memory.upsert_problem("a-th", "A", topic="dp")
                memory.upsert_problem("b-th", "B", topic="dp", status="solved")
                self.assertEqual(memory.current_problem()["slug"], "a-th")
            finally:
                memory.close()

    def test_similar_problems_match_topic_or_shared_failure_tag(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory(Path(d))
            try:
                dp = memory.upsert_problem("dp-one", "DP one", topic="dp")
                attempt = memory.add_attempt(dp, "code", verdict="WA")
                memory.add_failures(attempt, [{"tag": "wrong-state"}])

                graph = memory.upsert_problem("graph-one", "Graph one", topic="graph")
                attempt = memory.add_attempt(graph, "code", verdict="WA")
                memory.add_failures(attempt, [{"tag": "wrong-state"}])

                memory.upsert_problem("far-away", "Unrelated", topic="geometry")

                found = {p["slug"] for p in
                         memory.similar_problems("dp", ["wrong-state"], limit=5)}
                self.assertEqual(found, {"dp-one", "graph-one"})
            finally:
                memory.close()


class SchemaTests(unittest.TestCase):
    def good(self, **extra):
        return {"reply": "ลองดูที่ n ก่อน", "rung": 2, **extra}

    def test_a_minimal_reply_decodes(self):
        decoded = mentor.decode(self.good())
        self.assertEqual(decoded.text, "ลองดูที่ n ก่อน")
        self.assertEqual(decoded.rung, 2)
        self.assertIsNone(decoded.problem)
        self.assertEqual(decoded.failures, [])
        self.assertIsNone(decoded.note)

    def test_a_reply_can_never_carry_pc_actions(self):
        self.assertNotIn("actions", mentor.MENTOR_SCHEMA["properties"])
        decoded = mentor.decode(self.good(actions=[{"name": "open_app"}]))
        self.assertFalse(hasattr(decoded, "actions"))

    def test_an_unknown_topic_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(problem={"slug": "x", "title": "X",
                                             "topic": "quantum", "status": "working"}))

    def test_an_unknown_failure_tag_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(failures=[{"tag": "vibes-were-off"}]))

    def test_an_unknown_page_type_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(note={"slug": "s", "type": "blogpost",
                                          "tags": ["dp"], "lang": "th", "body": "x"}))

    def test_a_rung_outside_the_ladder_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode({"reply": "x", "rung": 9})

    def test_a_missing_reply_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode({"rung": 1})

    def test_a_slug_that_looks_like_a_path_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(note={"slug": "../escape", "type": "concept",
                                          "tags": ["dp"], "lang": "th", "body": "x"}))

    def test_a_well_formed_note_survives(self):
        decoded = mentor.decode(self.good(note={
            "slug": "monotonic-deque", "type": "concept", "tags": ["dp", "queue"],
            "lang": "both", "body": "คิวที่เก็บค่าเรียงลง"}))
        self.assertEqual(decoded.note["slug"], "monotonic-deque")
        self.assertEqual(decoded.note["type"], "concept")

    def test_an_attempt_flag_decodes(self):
        decoded = mentor.decode(self.good(attempt=True))
        self.assertTrue(decoded.attempt)

    def test_the_attempt_flag_defaults_to_false(self):
        decoded = mentor.decode(self.good())
        self.assertFalse(decoded.attempt)


class VerdictInTests(unittest.TestCase):
    def test_a_verdict_word_is_read_from_the_users_text(self):
        self.assertEqual(mentor.verdict_in("ส่งไปได้ WA ครับ"), "WA")
        self.assertEqual(mentor.verdict_in("ผ่านแล้ว AC"), "AC")

    def test_pasted_code_with_no_verdict_word_is_unsubmitted(self):
        self.assertEqual(mentor.verdict_in("#include <bits/stdc++.h>\nint main(){}"), "unsubmitted")

    def test_plain_reasoning_has_no_verdict(self):
        self.assertIsNone(mentor.verdict_in("ผมว่าน่าจะใช้ dp นะ"))

    def test_a_verdict_like_substring_inside_another_word_does_not_match(self):
        self.assertIsNone(mentor.verdict_in("SWATTEAM ทำสำเร็จ"))


class SystemPromptTests(unittest.TestCase):
    def test_the_prompt_states_the_rules_python_actually_enforces(self):
        for fragment in ("เปิดเฉลย", "C++", "ขั้น", "POSN"):
            self.assertIn(fragment, mentor.SYSTEM)

    def test_the_prompt_forbids_jumping_the_ladder(self):
        self.assertIn("ทีละขั้น", mentor.SYSTEM)

    def test_the_prompt_tells_the_model_it_has_no_tools(self):
        self.assertIn("ไม่สามารถเปิดไฟล์", mentor.SYSTEM)

    def test_notes_are_framed_as_the_users_assumptions_not_as_truth(self):
        self.assertIn("ไม่ใช่ข้อเท็จจริง", mentor.NOTE_FRAME)
        self.assertIn("ทางเลือกอื่น", mentor.NOTE_FRAME)

    def test_the_prompt_fits_its_slice_of_the_budget(self):
        self.assertLess(len(mentor.SYSTEM) + len(mentor.NOTE_FRAME), 1200)


class BudgetTests(unittest.TestCase):
    def oversized(self):
        return {
            "allowed": 3,
            "problem": {"slug": "knapsack-th", "title": "K" * 5000, "topic": "dp",
                        "status": "working", "rung": 2},
            "attempts": [{"body": "x" * 9000, "verdict": "WA"}],
            "profile": [("wrong-state", 4), ("off-by-one", 2)],
            "similar": [{"slug": f"p{n}", "title": "T" * 3000, "topic": "dp"}
                        for n in range(9)],
            "style_guide": "s" * 9000,
            "pages": ["p" * 9000, "q" * 9000, "r" * 9000],
            "turns": [{"role": "user", "text": "t" * 4000} for _ in range(40)],
        }

    def test_every_slice_is_capped_and_the_total_stays_under_the_limit(self):
        prompt = mentor.build_prompt(**self.oversized())
        self.assertLess(len(prompt), 21_000)

    def test_no_slice_is_dropped_entirely_when_everything_is_oversized(self):
        prompt = mentor.build_prompt(**self.oversized())
        for marker in ("knapsack-th", "wrong-state", "sss", "ppp", "ttt"):
            self.assertIn(marker, prompt)

    def test_the_allowed_rung_is_stated_to_the_model(self):
        prompt = mentor.build_prompt(**{**self.oversized(), "allowed": 4})
        self.assertIn("ขั้นที่อนุญาตรอบนี้: 4", prompt)

    def test_an_empty_profile_says_so_rather_than_being_silent(self):
        self.assertIn("ยังไม่มีข้อมูล", mentor.render_profile([]))

    def test_a_profile_ranks_what_the_user_gets_wrong(self):
        rendered = mentor.render_profile([("wrong-state", 4), ("off-by-one", 1)])
        self.assertIn("wrong-state", rendered)
        self.assertIn("4", rendered)

    def test_a_first_session_with_nothing_stored_still_builds_a_prompt(self):
        prompt = mentor.build_prompt(allowed=0, problem=None, attempts=[], profile=[],
                                     similar=[], style_guide="", pages=[], turns=[])
        self.assertIn("ขั้นที่อนุญาตรอบนี้: 0", prompt)
        self.assertIn("ยังไม่มีข้อมูล", prompt)


class RoutingTests(unittest.TestCase):
    def test_a_mentor_turn_asks_for_the_mentor_schema_and_higher_effort(self):
        import claude_brain
        captured = {}

        def fake_request(model, system, schema, content, cancelled=None, effort="low"):
            captured.update(model=model, system=system, schema=schema,
                            content=content, effort=effort)
            return {"reply": "ลองดู n ก่อน", "rung": 1}

        with patch.object(claude_brain, "_request", fake_request):
            decoded = claude_brain.ask_mentor("sonnet", "ข้อนี้ทำไงดี")

        self.assertEqual(decoded.text, "ลองดู n ก่อน")
        self.assertEqual(captured["schema"], mentor.MENTOR_SCHEMA)
        self.assertNotIn("actions", captured["schema"]["properties"])
        self.assertIn("POSN", captured["system"])
        self.assertEqual(captured["effort"], "medium")
        self.assertEqual(captured["content"], [{"type": "text", "text": "ข้อนี้ทำไงดี"}])

    def test_a_malformed_mentor_reply_is_refused_not_displayed(self):
        import claude_brain
        with patch.object(claude_brain, "_request",
                          lambda *a, **k: {"reply": "x", "rung": 99}):
            with self.assertRaises(mentor.MentorError):
                claude_brain.ask_mentor("sonnet", "ข้อนี้ทำไงดี")

    def test_mentor_mode_refuses_a_gemini_model(self):
        import engine
        from brain import BrainError
        with self.assertRaises(BrainError):
            engine.ask_mentor("gemini-3.8-flash", "ข้อนี้ทำไงดี")


if __name__ == "__main__":
    unittest.main()
