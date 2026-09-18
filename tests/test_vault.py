from pathlib import Path
import os
import tempfile
import unittest

from vault import Vault, VaultError

PAGE = """---
name: {slug}
type: {type}
tags: [{tags}]
lang: th
sources: 1
date: 2026-09-17
---

{body}
"""


def build(root: Path, pages):
    (root / "wiki").mkdir(parents=True)
    (root / "raw" / "assets").mkdir(parents=True)
    (root / "index.md").write_text("# Wiki Index", encoding="utf-8")
    (root / "log.md").write_text("# Log", encoding="utf-8")
    for slug, kind, tags, body in pages:
        (root / "wiki" / f"{slug}.md").write_text(
            PAGE.format(slug=slug, type=kind, tags=", ".join(tags), body=body),
            encoding="utf-8")


class CatalogueTests(unittest.TestCase):
    def test_the_catalogue_reads_frontmatter_from_every_page(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("monotonic-deque", "concept", ["dp", "queue"], "เนื้อหา"),
                         ("style-guide", "entity", ["meta"], "สไตล์ของผม")])
            entries = {e["slug"]: e for e in Vault(root).catalogue()}
            self.assertEqual(set(entries), {"monotonic-deque", "style-guide"})
            self.assertEqual(entries["monotonic-deque"]["type"], "concept")
            self.assertEqual(entries["monotonic-deque"]["tags"], ["dp", "queue"])
            self.assertEqual(entries["style-guide"]["date"], "2026-09-17")

    def test_a_page_without_frontmatter_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("good", "concept", ["dp"], "ok")])
            (root / "wiki" / "broken.md").write_text("no frontmatter", encoding="utf-8")
            self.assertEqual([e["slug"] for e in Vault(root).catalogue()], ["good"])

    def test_a_missing_vault_reports_itself_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VaultError):
                Vault(Path(d) / "not-here").catalogue()

    def test_invalid_utf8_pages_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("good", "concept", ["dp"], "ok")])
            (root / "wiki" / "broken-encoding.md").write_bytes(b"\xff\xfe---")
            entries = [e["slug"] for e in Vault(root).catalogue()]
            self.assertEqual(entries, ["good"])

    def test_in_place_edits_are_noticed_by_same_vault_instance(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("page", "concept", ["dp"], "body")])
            vault = Vault(root)
            self.assertEqual([e["slug"] for e in vault.catalogue()], ["page"])
            self.assertEqual(vault.catalogue()[0]["tags"], ["dp"])
            # Edit the page in place with new tags
            page_path = root / "wiki" / "page.md"
            (page_path).write_text(
                PAGE.format(slug="page", type="concept", tags="graph, dp", body="body"),
                encoding="utf-8")
            # Force mtime change to trigger cache invalidation
            t = page_path.stat().st_mtime_ns
            os.utime(page_path, ns=(t + 10**9, t + 10**9))
            # Second call should see new tags
            entries = vault.catalogue()
            self.assertEqual(entries[0]["tags"], ["graph", "dp"])


class SelectionTests(unittest.TestCase):
    def test_pages_are_selected_by_tag_overlap_and_capped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("dp-note", "concept", ["dp"], "ก" * 4000),
                         ("graph-note", "concept", ["graph"], "ข" * 4000),
                         ("shared", "concept", ["dp", "graph"], "ค" * 4000)])
            chosen = Vault(root).select("dp", [], limit=2, budget=1500)
            self.assertEqual(len(chosen), 2)
            self.assertLessEqual(sum(len(c) for c in chosen), 1500)
            self.assertTrue(any("dp-note" in c or "shared" in c for c in chosen))
            self.assertFalse(any("graph-note" in c for c in chosen))

    def test_the_style_guide_is_found_by_slug_and_capped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("style-guide", "entity", ["meta"], "ส" * 4000)])
            guide = Vault(root).style_guide(budget=1500)
            self.assertLessEqual(len(guide), 1500)
            self.assertIn("ส", guide)

    def test_a_missing_style_guide_is_an_empty_string_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("dp-note", "concept", ["dp"], "x")])
            self.assertEqual(Vault(root).style_guide(), "")


if __name__ == "__main__":
    unittest.main()
