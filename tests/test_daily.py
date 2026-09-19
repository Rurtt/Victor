from datetime import date, timedelta
from pathlib import Path
import random
import tempfile
import unittest

from bank import Entry
import daily
from memory import Memory

D0 = date(2026, 9, 20)


def row(day, role="main", level=1, ac=False, graded=None, status="working", rung=0):
    return {"day": day.isoformat(), "role": role, "level": level, "ac": ac,
            "graded": ac if graded is None else graded, "status": status, "rung": rung}


def entry(slug, level, topic="implementation"):
    ident = f"camp1/{slug}" if level <= 2 else slug
    return Entry(id=ident, slug=slug, title=slug.title(), level=level, topic=topic,
                 time_limit=1.0, statement=f"# {slug}\n", tests=(("1\n", "1\n"),),
                 url=None if level <= 2 else f"https://example.org/{slug}")


class NextLevelTests(unittest.TestCase):
    def step(self, level, rows, today, last_change=None):
        return daily.next_level(level, rows, today=today, camp1_started=D0,
                                last_change=last_change)

    def test_day_one_with_six_acs_stays_in_camp_one(self):
        rows = [row(D0, ac=True) for _ in range(6)]
        self.assertEqual(self.step(1, rows, D0)[0], 2)
        self.assertEqual(self.step(2, rows, D0, last_change=D0)[0], 2)
        second_day = [row(D0, level=2, ac=True) for _ in range(6)]
        self.assertEqual(self.step(2, second_day, D0 + timedelta(1))[0], 2)

    def test_third_day_with_five_of_six_moves_to_camp_two(self):
        rows = [row(D0, level=2, ac=True) for _ in range(5)] + [row(D0, level=2, graded=True)]
        self.assertEqual(self.step(2, rows, D0 + timedelta(2))[0], 3)

    def test_four_of_six_is_not_enough(self):
        rows = ([row(D0, level=2, ac=True) for _ in range(4)]
                + [row(D0, level=2, graded=True) for _ in range(2)])
        self.assertEqual(self.step(2, rows, D0 + timedelta(2))[0], 2)

    def test_ungraded_rows_do_not_count_against_promotion(self):
        rows = ([row(D0, level=2, ac=True) for _ in range(5)]
                + [row(D0, level=2) for _ in range(3)])
        self.assertEqual(self.step(2, rows, D0 + timedelta(2))[0], 3)

    def test_fourth_day_forces_camp_two(self):
        day4 = D0 + timedelta(3)
        self.assertEqual(self.step(1, [], day4), (3, "Camp 1 ceiling: day 4"))
        self.assertEqual(self.step(2, [], day4, last_change=day4)[0], 3)

    def test_three_low_hint_solves_step_up(self):
        change = D0 + timedelta(3)
        rows = [row(change + timedelta(i + 1), level=3, ac=True, rung=2) for i in range(3)]
        self.assertEqual(self.step(3, rows, change + timedelta(4), last_change=change)[0], 4)

    def test_a_heavily_hinted_solve_blocks_step_up(self):
        change = D0 + timedelta(3)
        rows = [row(change + timedelta(i + 1), level=3, ac=True, rung=r)
                for i, r in enumerate((2, 3, 1))]
        self.assertEqual(self.step(3, rows, change + timedelta(4), last_change=change)[0], 3)

    def test_warmups_do_not_count_toward_camp_two_steps(self):
        change = D0 + timedelta(3)
        rows = [row(change + timedelta(i + 1), role="warmup", level=3, ac=True) for i in range(3)]
        self.assertEqual(self.step(3, rows, change + timedelta(4), last_change=change)[0], 3)

    def test_two_give_ups_step_down_but_never_below_three(self):
        change = D0 + timedelta(5)
        gave_up = [row(change + timedelta(i + 1), level=4, status="given-up") for i in range(2)]
        self.assertEqual(self.step(4, gave_up, change + timedelta(3), last_change=change)[0], 3)
        at_three = [dict(r, level=3) for r in gave_up]
        self.assertEqual(self.step(3, at_three, change + timedelta(3), last_change=change)[0], 3)

    def test_only_one_change_per_day(self):
        today = D0 + timedelta(8)
        rows = [row(D0 + timedelta(4 + i), level=3, ac=True) for i in range(3)]
        self.assertEqual(self.step(3, rows, today, last_change=today)[0], 3)

    def test_problems_from_before_the_last_change_are_ignored(self):
        change = D0 + timedelta(5)
        rows = [row(change - timedelta(i), level=3, ac=True) for i in range(3)]
        self.assertEqual(self.step(3, rows, change + timedelta(1), last_change=change)[0], 3)


class ServeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.memory = Memory(base)
        self.root = base / "daily"
        self.rng = random.Random(7)

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def serve(self, entries, today=D0, **kw):
        return daily.ensure_today(self.memory, entries, self.root, today, rng=self.rng, **kw)

    def test_serving_is_idempotent_on_the_same_day(self):
        entries = [entry("a", 1), entry("b", 1), entry("c", 1)]
        self.assertEqual(self.serve(entries), [])
        self.assertEqual(self.serve(entries), [])
        rows = self.memory.daily_rows(D0.isoformat())
        self.assertEqual([r["role"] for r in rows], ["warmup", "main"])
        for role in ("main", "warmup"):
            folder = daily.folder(self.root, D0, role)
            self.assertTrue((folder / "statement.md").exists())
            self.assertEqual((folder / "sol.cpp").read_text(encoding="utf-8"), daily.TEMPLATE)

    def test_a_problem_is_never_served_twice(self):
        entries = [entry(s, 1) for s in ("a", "b", "c", "d")]
        self.serve(entries)
        self.serve(entries, today=D0 + timedelta(1))
        sources = [r["source"] for r in self.memory.daily_rows()]
        self.assertEqual(len(sources), 4)
        self.assertEqual(len(set(sources)), 4)

    def test_warmup_is_one_level_below_main(self):
        self.memory.set_meta("camp1_started", (D0 - timedelta(10)).isoformat())
        self.memory.set_meta("level", 3)
        self.serve([entry("easy", 2), entry("real", 3, topic="dp")])
        rows = {r["role"]: r for r in self.memory.daily_rows(D0.isoformat())}
        self.assertEqual((rows["warmup"]["level"], rows["main"]["level"]), (2, 3))

    def test_exhausted_level_falls_back_with_a_notice(self):
        self.memory.set_meta("camp1_started", (D0 - timedelta(10)).isoformat())
        self.memory.set_meta("level", 3)
        notices = self.serve([entry("easy", 2), entry("hard", 4, topic="dp")])
        rows = {r["role"]: r for r in self.memory.daily_rows(D0.isoformat())}
        self.assertEqual(rows["main"]["level"], 4)
        self.assertTrue(any("level 4" in n for n in notices))

    def test_empty_bank_serves_nothing_and_retries_later(self):
        notices = self.serve([])
        self.assertEqual(self.memory.daily_rows(), [])
        self.assertTrue(notices)
        self.assertIsNone(self.memory.get_meta("last_daily"))

    def test_weak_topic_is_preferred(self):
        weak = self.memory.upsert_problem("old", "Old", topic="string")
        self.memory.add_failures(self.memory.add_attempt(weak, "x"), [{"tag": "off-by-one"}])
        entries = [entry(f"i{n}", 1) for n in range(6)] + [entry("s", 1, topic="string")]
        self.serve(entries)
        served = {r["source"] for r in self.memory.daily_rows(D0.isoformat())}
        self.assertIn("camp1/s", served)

    def test_ceiling_change_is_logged(self):
        self.memory.set_meta("camp1_started", (D0 - timedelta(3)).isoformat())
        logged = []
        notices = self.serve([entry("easy", 2), entry("real", 3, topic="dp")],
                             log=lambda title, text: logged.append(title))
        self.assertEqual(logged, ["Level 1 → 3"])
        self.assertEqual(self.memory.get_meta("level"), "3")
        self.assertTrue(any("Level 1 → 3" in n for n in notices))

    def test_existing_solution_is_never_overwritten(self):
        target = daily.write_folder(self.root, D0, "main", entry("a", 1))
        (target / "sol.cpp").write_text("my work", encoding="utf-8")
        daily.write_folder(self.root, D0, "main", entry("a", 1))
        self.assertEqual((target / "sol.cpp").read_text(encoding="utf-8"), "my work")

    def test_folder_rejects_unknown_roles(self):
        with self.assertRaises(ValueError):
            daily.folder(self.root, D0, "..")
