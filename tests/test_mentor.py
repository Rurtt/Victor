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


if __name__ == "__main__":
    unittest.main()
