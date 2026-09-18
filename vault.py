"""Read and write a study vault that follows the existing Obsidian schema.

The schema is not ours to invent — it is D:\\Jarvis\\Luk Nong Pong\\CLAUDE.md, reused
verbatim. Page content is the user's own notes: treated as his assumptions, and as
untrusted text when it reaches a prompt. Nothing here ever writes to raw/.
"""
from __future__ import annotations

from pathlib import Path
from datetime import date
import re

STYLE_GUIDE = "style-guide"
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MAX_PAGE = 100_000

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TYPE_ORDER = ("source", "concept", "entity", "synthesis", "query")
TYPE_HEADING = {"source": "Sources", "concept": "Concepts", "entity": "Entities",
                "synthesis": "Syntheses", "query": "Queries"}


class VaultError(RuntimeError):
    pass


def _parse_list(raw: str) -> list[str]:
    inner = raw.strip().strip("[]")
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def _frontmatter(text: str) -> dict | None:
    match = FRONTMATTER.match(text)
    if not match:
        return None
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if "name" not in fields or "type" not in fields:
        return None
    return {"slug": fields["name"], "type": fields["type"],
            "tags": _parse_list(fields.get("tags", "")),
            "lang": fields.get("lang", "both"), "date": fields.get("date", "")}


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.wiki = self.root / "wiki"
        self.log = self.root / "log.md"
        self.index = self.root / "index.md"
        self._cache: list[dict] | None = None
        self._stamp = None

    def catalogue(self) -> list[dict]:
        """Frontmatter only, cached against each page's mtime."""
        if not self.wiki.is_dir():
            raise VaultError(f"ไม่พบ wiki ที่ {self.wiki}")
        stamp = tuple((p.name, p.stat().st_mtime_ns) for p in sorted(self.wiki.glob("*.md")))
        if self._cache is not None and stamp == self._stamp:
            return self._cache
        entries = []
        for path in sorted(self.wiki.glob("*.md")):
            try:
                head = path.read_text(encoding="utf-8")[:4000]
            except (OSError, UnicodeDecodeError):
                continue
            fields = _frontmatter(head)
            if fields:
                entries.append({**fields, "path": path})
        self._cache, self._stamp = entries, stamp
        return entries

    def page(self, slug: str) -> str:
        for entry in self.catalogue():
            if entry["slug"] == slug:
                return entry["path"].read_text(encoding="utf-8", errors="replace")[:MAX_PAGE]
        return ""

    def select(self, topic: str, tags, limit: int = 2, budget: int = 1500) -> list[str]:
        """Pages whose tags overlap the current topic. No model call to choose."""
        wanted = {topic, *(tags or [])}
        ranked = sorted(
            (e for e in self.catalogue()
             if e["slug"] != STYLE_GUIDE and wanted & set(e["tags"])),
            key=lambda e: (-len(wanted & set(e["tags"])), e["slug"]))
        chosen, spent = [], 0
        share = budget // max(1, min(limit, len(ranked) or 1))
        for entry in ranked[:limit]:
            text = entry["path"].read_text(encoding="utf-8", errors="replace")[:share]
            if spent + len(text) > budget:
                text = text[:budget - spent]
            if not text:
                break
            chosen.append(text)
            spent += len(text)
        return chosen

    def style_guide(self, budget: int = 1500) -> str:
        return self.page(STYLE_GUIDE)[:budget]

    def _destination(self, slug: str) -> Path:
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or len(slug) > 120:
            raise VaultError("slug ต้องเป็น kebab-case และห้ามมีเส้นทางไฟล์")
        path = (self.wiki / f"{slug}.md").resolve()
        if path.parent != self.wiki.resolve():
            raise VaultError("หน้า wiki ต้องอยู่ในโฟลเดอร์ wiki เท่านั้น")
        return path

    def render(self, note: dict, *, sources: int = 1, today: str | None = None) -> str:
        today = today or date.today().isoformat()
        tags = ", ".join(note.get("tags") or [])
        return (f"---\nname: {note['slug']}\ntype: {note['type']}\n"
                f"tags: [{tags}]\nlang: {note['lang']}\nsources: {sources}\n"
                f"date: {today}\n---\n\n{note['body'].strip()}\n")

    def save(self, note: dict, summary: str, *, today: str | None = None) -> Path:
        """Write one page, then refresh index.md and append to log.md.

        The user has already approved this page in the desktop UI; the checks here
        are against a malformed slug, not against the user's intent.
        """
        destination = self._destination(note["slug"])
        existed = destination.exists()
        sources = 1
        if existed:
            previous = destination.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"^sources:\s*(\d+)", previous, re.MULTILINE)
            sources = int(match.group(1)) + 1 if match else 2
        destination.write_text(self.render(note, sources=sources, today=today),
                               encoding="utf-8")
        self._cache = None  # the catalogue is stale now
        self.rebuild_index(today=today)
        self.append_log("update" if existed else "ingest", note["slug"], summary,
                        today=today)
        return destination

    def rebuild_index(self, today: str | None = None):
        today = today or date.today().isoformat()
        entries = self.catalogue()
        lines = [f"# Wiki Index\nLast updated: {today} | Total pages: {len(entries)}\n"]
        for kind in TYPE_ORDER:
            group = [e for e in entries if e["type"] == kind]
            if not group:
                continue
            lines.append(f"## {TYPE_HEADING[kind]} ({len(group)})")
            lines += [f"- [[{e['slug']}]]" for e in group]
            lines.append("")
        self.index.write_text("\n".join(lines), encoding="utf-8")

    def append_log(self, action: str, title: str, description: str,
                   today: str | None = None):
        today = today or date.today().isoformat()
        if action not in ("ingest", "query", "lint", "update"):
            raise VaultError("action ของ log ไม่ถูกต้อง")
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## [{today}] {action} | {title}\n{description}\n")
