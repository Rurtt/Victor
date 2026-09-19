import json
from pathlib import Path
import tempfile
import unittest

import bank

ROOT = Path(__file__).resolve().parent.parent


def camp1(root, folder_name, **meta):
    # Use folder_name as the positional parameter, with slug in meta optionally overriding
    meta_slug = meta.pop("slug", folder_name)
    folder = root / "camp1" / folder_name
    (folder / "tests").mkdir(parents=True)
    data = {"slug": meta_slug, "title": "Sum", "level": 1, "topic": "implementation",
            "time_limit": 1.0, **meta}
    (folder / "meta.json").write_text(json.dumps(data), encoding="utf-8")
    (folder / "statement.md").write_text("# Sum\n", encoding="utf-8")
    (folder / "tests" / "01.in").write_text("1 2\n", encoding="utf-8")
    (folder / "tests" / "01.out").write_text("3\n", encoding="utf-8")
    return folder


ARCHIVE_ITEM = {"id": "pith-0001", "title": "Example", "url": "https://example.org/t/1",
                "level": 3, "topic": "dp", "samples": [{"in": "3\n", "out": "6\n"}]}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_archive(self, items):
        (self.root / "archive.json").write_text(json.dumps(items), encoding="utf-8")

    def test_loads_camp1_and_archive(self):
        camp1(self.root, "sum-two")
        self.write_archive([ARCHIVE_ITEM])
        first, second = bank.load(self.root)
        self.assertEqual((first.id, first.level, first.url), ("camp1/sum-two", 1, None))
        self.assertEqual(first.tests[0][0].name, "01.in")
        self.assertEqual((second.id, second.slug, second.level), ("pith-0001", "pith-0001", 3))
        self.assertEqual(second.tests, (("3\n", "6\n"),))
        self.assertIn("https://example.org/t/1", second.statement)

    def test_empty_root_is_an_empty_bank(self):
        self.assertEqual(bank.load(self.root), [])

    def test_unknown_topic_is_rejected(self):
        camp1(self.root, "sum-two", topic="magic")
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_camp1_level_must_be_one_or_two(self):
        camp1(self.root, "sum-two", level=3)
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_boolean_level_is_rejected(self):
        camp1(self.root, "sum-two", level=True)
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_slug_must_match_folder(self):
        camp1(self.root, "sum-two", slug="other")
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_input_without_output_is_rejected(self):
        folder = camp1(self.root, "sum-two")
        (folder / "tests" / "02.in").write_text("1 1\n", encoding="utf-8")
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_archive_needs_https_and_samples(self):
        self.write_archive([dict(ARCHIVE_ITEM, url="http://example.org")])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)
        self.write_archive([dict(ARCHIVE_ITEM, samples=[])])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_archive_must_have_url(self):
        # Archive items require a URL; missing url key should raise BankError
        item_without_url = dict(ARCHIVE_ITEM)
        del item_without_url["url"]
        self.write_archive([item_without_url])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_archive_rejects_a_null_url(self):
        # A present-but-null url key must be rejected the same as a missing key.
        self.write_archive([dict(ARCHIVE_ITEM, url=None)])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_duplicate_ids_are_rejected(self):
        self.write_archive([ARCHIVE_ITEM, ARCHIVE_ITEM])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)


class CommittedBankTests(unittest.TestCase):
    def test_camp1_bank_is_large_enough_for_the_first_days(self):
        entries = [e for e in bank.load(ROOT / "problems") if e.url is None]
        by_level = {level: [e for e in entries if e.level == level] for level in (1, 2)}
        self.assertGreaterEqual(len(by_level[1]), 10)
        self.assertGreaterEqual(len(by_level[2]), 10)
        self.assertGreaterEqual(len({e.topic for e in entries}), 4)
        for entry in entries:
            self.assertGreaterEqual(len(entry.tests), 10, entry.id)

    def test_archive_covers_every_camp2_level(self):
        entries = [e for e in bank.load(ROOT / "problems") if e.url is not None]
        self.assertGreaterEqual(len(entries), 30)
        for level in (3, 4, 5):
            self.assertGreaterEqual(len([e for e in entries if e.level == level]), 8, level)
