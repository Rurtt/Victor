"""The problem bank: verified Camp-1 problems in problems/camp1, Camp-2 links in archive.json.

Everything here is repository content, reviewed before commit, but it is still
validated on load so that one bad meta.json is a clear error, not a crash later.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from memory import TOPICS

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CAMP1_LEVELS = (1, 2)
ARCHIVE_LEVELS = (3, 4, 5)


class BankError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    id: str
    slug: str
    title: str
    level: int
    topic: str
    time_limit: float
    statement: str
    tests: tuple
    url: str | None = None


def _check(entry: Entry, levels) -> Entry:
    name = entry.id or "?"
    if not isinstance(entry.slug, str) or not SLUG.fullmatch(entry.slug) or len(entry.slug) > 120:
        raise BankError(f"{name}: slug must be kebab-case")
    if not entry.title.strip():
        raise BankError(f"{name}: empty title")
    if isinstance(entry.level, bool) or entry.level not in levels:
        raise BankError(f"{name}: level must be one of {levels}")
    if entry.topic not in TOPICS:
        raise BankError(f"{name}: unknown topic {entry.topic!r}")
    limit = entry.time_limit
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not 0 < limit <= 10:
        raise BankError(f"{name}: time_limit must be between 0 and 10 seconds")
    if not entry.tests:
        raise BankError(f"{name}: no tests")
    if entry.url is not None and not (isinstance(entry.url, str) and entry.url.startswith("https://")):
        raise BankError(f"{name}: url must start with https://")
    return entry


def _camp1(folder: Path) -> Entry:
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        statement = (folder / "statement.md").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise BankError(f"{folder.name}: {exc}") from None
    if not isinstance(meta, dict) or meta.get("slug") != folder.name:
        raise BankError(f"{folder.name}: meta.json slug must match the folder name")
    tests = []
    for given in sorted((folder / "tests").glob("*.in")):
        expected = given.with_suffix(".out")
        if not expected.exists():
            raise BankError(f"{folder.name}: {given.name} has no .out")
        tests.append((given, expected))
    return _check(Entry(id=f"camp1/{folder.name}", slug=folder.name,
                        title=str(meta.get("title", "")), level=meta.get("level"),
                        topic=meta.get("topic"), time_limit=meta.get("time_limit"),
                        statement=statement, tests=tuple(tests)), CAMP1_LEVELS)


def _archive(item) -> Entry:
    if not isinstance(item, dict):
        raise BankError("archive.json: every entry must be an object")
    samples = item.get("samples") or []
    if not all(isinstance(s, dict) and isinstance(s.get("in"), str)
               and isinstance(s.get("out"), str) for s in samples):
        raise BankError(f"{item.get('id')}: samples must be {{in, out}} strings")
    # Archive items must have a URL (unlike Camp-1 which can be None)
    if "url" not in item:
        raise BankError(f"{item.get('id')}: archive item must have a url key")
    ident, title = str(item.get("id", "")), str(item.get("title", ""))
    lines = [f"# {title}", "",
             f"Level {item.get('level')} · {item.get('topic')} · real judge problem", "",
             f"Full statement and submission: {item.get('url')}", ""]
    for n, sample in enumerate(samples, 1):
        lines += [f"## Sample {n}", "", "Input:", "```", sample["in"].rstrip("\n"), "```",
                  "Output:", "```", sample["out"].rstrip("\n"), "```", ""]
    return _check(Entry(id=ident, slug=ident, title=title, level=item.get("level"),
                        topic=item.get("topic"), time_limit=item.get("time_limit", 1.0),
                        statement="\n".join(lines),
                        tests=tuple((s["in"], s["out"]) for s in samples),
                        url=item.get("url")), ARCHIVE_LEVELS)


def load(root: Path) -> list[Entry]:
    root = Path(root)
    camp1 = root / "camp1"
    entries = [_camp1(d) for d in sorted(camp1.iterdir()) if d.is_dir()] if camp1.is_dir() else []
    archive = root / "archive.json"
    if archive.exists():
        try:
            items = json.loads(archive.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BankError(f"archive.json: {exc}") from None
        if not isinstance(items, list):
            raise BankError("archive.json must be a list")
        entries += [_archive(i) for i in items]
    for field in ("id", "slug"):
        values = [getattr(e, field) for e in entries]
        if len(values) != len(set(values)):
            raise BankError(f"duplicate {field} in the problem bank")
    return entries
