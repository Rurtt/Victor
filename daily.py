"""Today's problems and the difficulty ramp. Policy lives here, never in a prompt.

The model never proposes a level. Levels move only on measured results: graded
verdicts, the hint rung reached, and recorded give-ups (spec section 5).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import random

from memory import DAILY_ROLES

CAMP1_MAX = 2
FIRST_CAMP2 = 3
MAX_LEVEL = 5
FLOOR_DAYS = 2          # earliest Camp 2 is the third day
CEILING_DAYS = 3        # the fourth day is Camp 2 no matter what
LEVEL2_AFTER = 3        # level-1 ACs before level 2
PROMOTE_WINDOW, PROMOTE_NEED = 6, 5
STEP_UP_STREAK, STEP_UP_MAX_RUNG = 3, 2
STEP_DOWN_STREAK = 2

TEMPLATE = """#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    return 0;
}
"""


def next_level(level, rows, *, today, camp1_started, last_change):
    """(new level, reason). Pure: rows come from Memory.daily_rows()."""
    days = (today - camp1_started).days
    if level <= CAMP1_MAX and days >= CEILING_DAYS:
        return FIRST_CAMP2, f"Camp 1 ceiling: day {days + 1}"
    if last_change == today:
        return level, ""
    if level <= CAMP1_MAX:
        graded = [r for r in rows if r["level"] <= CAMP1_MAX and r["graded"]][-PROMOTE_WINDOW:]
        if days >= FLOOR_DAYS and sum(r["ac"] for r in graded) >= PROMOTE_NEED:
            return FIRST_CAMP2, f"{PROMOTE_NEED} of the last {PROMOTE_WINDOW} Camp-1 problems solved"
        if level == 1 and sum(r["ac"] for r in rows if r["level"] == 1) >= LEVEL2_AFTER:
            return 2, f"{LEVEL2_AFTER} level-1 problems solved"
        return level, ""
    since = last_change.isoformat() if last_change else ""
    outcomes = [("given-up" if r["status"] == "given-up" else "solved", r["rung"])
                for r in rows
                if r["role"] == "main" and r["level"] == level and r["day"] > since
                and (r["status"] == "given-up" or r["ac"])]
    tail = outcomes[-STEP_UP_STREAK:]
    if (level < MAX_LEVEL and len(tail) == STEP_UP_STREAK
            and all(o == "solved" and rung <= STEP_UP_MAX_RUNG for o, rung in tail)):
        return level + 1, f"{STEP_UP_STREAK} main problems solved with few hints"
    tail = outcomes[-STEP_DOWN_STREAK:]
    if (level > FIRST_CAMP2 and len(tail) == STEP_DOWN_STREAK
            and all(o == "given-up" for o, _ in tail)):
        return level - 1, f"{STEP_DOWN_STREAK} give-ups in a row"
    return level, ""


def update_level(memory, today, log=lambda title, text: None) -> str:
    level = int(memory.get_meta("level", "1"))
    started = date.fromisoformat(memory.get_meta("camp1_started", today.isoformat()))
    change = memory.get_meta("last_level_change")
    new, reason = next_level(level, memory.daily_rows(), today=today, camp1_started=started,
                             last_change=date.fromisoformat(change) if change else None)
    if new == level:
        return ""
    memory.set_meta("level", new)
    memory.set_meta("last_level_change", today.isoformat())
    title = f"Level {level} → {new}"
    log(title, reason)
    return f"{title}: {reason}"


def folder(root, today, role) -> Path:
    # Built only from the date and a fixed role name; never from bank or model text.
    if role not in DAILY_ROLES:
        raise ValueError(f"unknown daily role {role!r}")
    return Path(root) / today.isoformat() / role


def write_folder(root, today, role, entry) -> Path:
    target = folder(root, today, role)
    target.mkdir(parents=True, exist_ok=True)
    (target / "statement.md").write_text(entry.statement, encoding="utf-8")
    solution = target / "sol.cpp"
    if not solution.exists():
        solution.write_text(TEMPLATE, encoding="utf-8")
    return target


def _pick(entries, level, served, weak, rng, exclude):
    pool = [e for e in entries if e.level == level and e.id not in served and e.id not in exclude]
    for topic in weak:
        preferred = [e for e in pool if e.topic == topic]
        if preferred:
            return rng.choice(preferred)
    return rng.choice(pool) if pool else None


def _pick_near(entries, level, served, weak, rng, exclude=()):
    """The wanted level if it has problems left, else the nearest level that does."""
    # Ties go to the harder level: a Camp-2 student should not fall back into Camp 1.
    for candidate in sorted(range(1, MAX_LEVEL + 1), key=lambda n: (abs(n - level), -n)):
        found = _pick(entries, candidate, served, weak, rng, exclude)
        if found:
            return found
    return None


def ensure_today(memory, entries, root, today, *, rng=None, log=lambda title, text: None):
    """Serve today's warm-up and main exactly once. Returns notices for the transcript."""
    day = today.isoformat()
    if memory.get_meta("last_daily") == day:
        return []
    rng = rng or random.Random()
    if memory.get_meta("camp1_started") is None:
        memory.set_meta("camp1_started", day)
    notices = [n for n in [update_level(memory, today, log)] if n]
    level = int(memory.get_meta("level", "1"))
    served, weak = memory.served_sources(), memory.weak_topics()
    main = _pick_near(entries, level, served, weak, rng)
    if main is None:
        return notices + ["The problem bank is empty. Add problems under problems/."]
    if main.level != level:
        notices.append(f"No level-{level} problems left; today's main is level {main.level}.")
    warmup = _pick_near(entries, max(1, level - 1), served, weak, rng, exclude={main.id})
    picked = [("warmup", warmup), ("main", main)] if warmup else [("main", main)]
    for role, item in picked:  # every folder first, so a disk error leaves no DB rows
        write_folder(root, today, role, item)
    for role, item in picked:
        problem_id = memory.upsert_problem(item.slug, item.title, topic=item.topic, source=item.id)
        memory.add_daily(day, role, problem_id, item.level)
    memory.set_meta("last_daily", day)
    return notices
