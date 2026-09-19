"""Offline Camp-1 bank builder. Run by the developer, never by Victor.

    python tools/make_problem.py --level 1 --topic implementation --count 3

Claude proposes a problem with a reference solution, a brute force and an input
generator. A candidate is kept only if reference and brute force agree on every
small random input and the reference fits the time limit on maximum-size input.
Expected outputs come from the reference, never from Claude's own guesses.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bank  # noqa: E402
import grader  # noqa: E402
from memory import TOPICS  # noqa: E402

BANK = ROOT / "problems"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "slug", "statement", "reference_cpp", "brute_cpp", "gen_py",
                 "time_limit"],
    "properties": {
        "title": {"type": "string"}, "slug": {"type": "string"},
        "statement": {"type": "string"}, "reference_cpp": {"type": "string"},
        "brute_cpp": {"type": "string"}, "gen_py": {"type": "string"},
        "time_limit": {"type": "number"}}}

SYSTEM = """You write original practice problems for POSN (Thai computer olympiad) Camp 1.
Level 1: input/output, loops, conditionals, arrays, simple strings.
Level 2: sorting, simple math, brute force, prefix sums.

Return JSON with:
- title, slug (kebab-case, a-z 0-9 and hyphens only)
- statement: English Markdown with sections Statement, Input, Output, Constraints,
  and at least one Sample (input and output in fenced blocks). Constraints must be exact.
- reference_cpp: the intended C++17 solution; must run within time_limit at maximum constraints.
- brute_cpp: an obviously correct C++17 solution; slow is fine.
- gen_py: a Python 3 script. argv[1] is an integer seed, argv[2] is "small" or "max".
  Seed the random module with argv[1]. "small" prints a tiny valid input the brute force
  can handle instantly; "max" prints a valid input at maximum constraints. Print exactly
  one input and nothing else.
- time_limit: seconds, 1.0 unless the problem needs more.
The answer must be unique for every valid input (no "print any" problems).
Do not copy existing judge problems."""


class Rejected(Exception):
    pass


def _compile(text: str, workdir: Path, name: str) -> Path:
    source, exe = workdir / f"{name}.cpp", workdir / f"{name}.exe"
    source.write_text(text, encoding="utf-8")
    error = grader.compile_source(source, exe)
    if error:
        raise Rejected(f"{name} does not compile:\n{error}")
    return exe


def _input(gen: Path, seed: int, size: str) -> str:
    try:
        done = subprocess.run([sys.executable, str(gen), str(seed), size], capture_output=True,
                              text=True, timeout=20, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        raise Rejected(f"generator failed on seed {seed} ({size}): {exc}") from None
    return done.stdout


def _output(exe: Path, data: str, timeout: float, what: str) -> tuple[str, float]:
    run = grader.run_program([exe], data, timeout, cwd=exe.parent)
    if run.code is None:
        raise Rejected(f"{what} timed out")
    if run.code != 0:
        raise Rejected(f"{what} exited with {run.code}")
    return run.out, run.elapsed


def verify(candidate: dict, workdir: Path, *, small=300, large=8, keep_small=12):
    workdir = Path(workdir)
    # Validate candidate structure before doing expensive work
    required = SCHEMA["required"]
    for key in required:
        if key not in candidate:
            raise Rejected(f"candidate missing required key: {key!r}")
        if candidate[key] is None:
            raise Rejected(f"candidate key {key!r} is None")
    # Validate string fields are actually strings
    for key in ["title", "slug", "statement", "reference_cpp", "brute_cpp", "gen_py"]:
        if not isinstance(candidate[key], str):
            raise Rejected(f"{key} must be a string, got {type(candidate[key]).__name__}")
    try:
        limit = float(candidate["time_limit"])
    except (TypeError, ValueError) as exc:
        raise Rejected(f"time_limit must be numeric, got {candidate['time_limit']!r}") from None
    reference = _compile(candidate["reference_cpp"], workdir, "reference")
    brute = _compile(candidate["brute_cpp"], workdir, "brute")
    gen = workdir / "gen.py"
    gen.write_text(candidate["gen_py"], encoding="utf-8")
    tests = []
    for seed in range(small):
        data = _input(gen, seed, "small")
        want, _ = _output(brute, data, 10, f"brute force on seed {seed}")
        got, _ = _output(reference, data, limit * 2, f"reference on seed {seed}")
        if want.split() != got.split():
            raise Rejected(f"reference disagrees with brute force on seed {seed}:\n{data[:300]}")
        if seed < keep_small:
            tests.append((data, got))
    for seed in range(large):
        data = _input(gen, 100_000 + seed, "max")
        got, elapsed = _output(reference, data, limit * 2, f"reference on max seed {seed}")
        if elapsed > limit:
            raise Rejected(f"reference took {elapsed:.2f}s on max input, limit {limit}s")
        tests.append((data, got))
    return tests


def write_entry(bank_root: Path, candidate: dict, level: int, topic: str, tests) -> Path:
    slug = candidate.get("slug", "")
    if not isinstance(slug, str) or not bank.SLUG.fullmatch(slug) or len(slug) > 120:
        raise Rejected(f"bad slug {slug!r}")
    target = Path(bank_root) / "camp1" / slug
    if target.exists():
        raise Rejected(f"{slug} already exists in the bank")
    (target / "tests").mkdir(parents=True)
    meta = {"slug": slug, "title": candidate["title"], "level": level, "topic": topic,
            "time_limit": float(candidate["time_limit"])}
    (target / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (target / "statement.md").write_text(candidate["statement"], encoding="utf-8")
    for n, (given, expected) in enumerate(tests, 1):
        (target / "tests" / f"{n:02}.in").write_text(given, encoding="utf-8", newline="\n")
        (target / "tests" / f"{n:02}.out").write_text(expected, encoding="utf-8", newline="\n")
    return target


def main():
    from claude_brain import _request  # imported late: tests never need Claude
    from brain import BrainError

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", type=int, choices=bank.CAMP1_LEVELS, required=True)
    parser.add_argument("--topic", choices=TOPICS, required=True)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--model", default="sonnet")
    args = parser.parse_args()
    for _ in range(args.count):
        camp1 = BANK / "camp1"
        existing = sorted(p.name for p in camp1.glob("*")) if camp1.exists() else []
        ask = (f"Level {args.level}, topic {args.topic}. "
               f"Existing slugs, do not repeat these ideas: {', '.join(existing) or 'none'}.")
        try:
            candidate = _request(args.model, SYSTEM, SCHEMA, [{"type": "text", "text": ask}],
                                 effort="medium")
        except BrainError as exc:
            print(f"rejected unknown: {exc}")
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="victor-bank-") as workdir:
                tests = verify(candidate, Path(workdir))
            target = write_entry(BANK, candidate, args.level, args.topic, tests)
            print(f"kept     {target}")
        except Rejected as exc:
            print(f"rejected {candidate.get('slug')}: {exc}")


if __name__ == "__main__":
    main()
