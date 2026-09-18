"""Read and write a study vault that follows the existing Obsidian schema.

The schema is not ours to invent — it is D:\\Jarvis\\Luk Nong Pong\\CLAUDE.md, reused
verbatim. Page content is the user's own notes: treated as his assumptions, and as
untrusted text when it reaches a prompt. Nothing here ever writes to raw/.
"""
from __future__ import annotations

from pathlib import Path
import re

STYLE_GUIDE = "style-guide"
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MAX_PAGE = 100_000


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
        """Frontmatter only, cached against the directory's mtime."""
        if not self.wiki.is_dir():
            raise VaultError(f"ไม่พบ wiki ที่ {self.wiki}")
        stamp = self.wiki.stat().st_mtime_ns
        if self._cache is not None and stamp == self._stamp:
            return self._cache
        entries = []
        for path in sorted(self.wiki.glob("*.md")):
            try:
                head = path.read_text(encoding="utf-8")[:4000]
            except OSError:
                continue
            fields = _frontmatter(head)
            if fields:
                entries.append({**fields, "path": path})
        self._cache, self._stamp = entries, stamp
        return entries

    def page(self, slug: str) -> str:
        for entry in self.catalogue():
            if entry["slug"] == slug:
                return entry["path"].read_text(encoding="utf-8")[:MAX_PAGE]
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
            text = entry["path"].read_text(encoding="utf-8")[:share]
            if spent + len(text) > budget:
                text = text[:budget - spent]
            if not text:
                break
            chosen.append(text)
            spent += len(text)
        return chosen

    def style_guide(self, budget: int = 1500) -> str:
        return self.page(STYLE_GUIDE)[:budget]
