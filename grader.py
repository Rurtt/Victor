"""Compile and judge the user's C++ locally. Verdicts here are measured, never guessed.

This is the user's own code on the user's own machine, so there is no sandbox
beyond a time limit and a working directory — the same as running it from an
editor (spec 7.1).
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import NamedTuple

FALLBACK_GXX = Path(r"C:\msys64\ucrt64\bin\g++.exe")
# -static: the MSYS2 runtime DLLs are not on PATH, so a dynamic sol.exe cannot start.
# Big stack: Windows gives 1 MB, and a recursive DFS at N = 1e5 would die with RE.
FLAGS = ["-std=c++17", "-O2", "-static", "-Wl,--stack,268435456"]
COMPILE_TIMEOUT = 60
MAX_OUTPUT = 64_000_000
MAX_SHOWN_INPUT = 500
_HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class GraderError(RuntimeError):
    pass


class Run(NamedTuple):
    code: int | None  # None when killed for exceeding the time limit
    out: str
    elapsed: float


class Result(NamedTuple):
    verdict: str
    passed: int
    total: int
    detail: str


def find_compiler() -> str:
    found = shutil.which("g++")
    if found:
        return found
    if FALLBACK_GXX.exists():
        return str(FALLBACK_GXX)
    raise GraderError(f"g++ not found on PATH or at {FALLBACK_GXX}")


def run_program(args, stdin_text, timeout, *, cwd=None, cancelled=lambda: False,
                merge_stderr=False) -> Run:
    """Run one process with stdin from memory, output bounded on disk."""
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as out:
        source.write(stdin_text.encode("utf-8"))
        source.seek(0)
        if cancelled():
            raise GraderError("Stopped")
        start = time.monotonic()
        process = subprocess.Popen(
            [str(a) for a in args], stdin=source, stdout=out,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.DEVNULL,
            cwd=cwd, shell=False, creationflags=_HIDDEN)
        try:
            while process.poll() is None:
                if cancelled():
                    raise GraderError("Stopped")
                if time.monotonic() - start > timeout:
                    return Run(None, "", timeout)
                if os.fstat(out.fileno()).st_size > MAX_OUTPUT:
                    return Run(-1, "", time.monotonic() - start)
                time.sleep(0.005)
            elapsed = time.monotonic() - start
            out.seek(0)
            return Run(process.returncode, out.read(MAX_OUTPUT).decode("utf-8", "replace"), elapsed)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def compile_source(source: Path, exe: Path, *, cancelled=lambda: False) -> str | None:
    """None on success, otherwise the first 20 lines of compiler output."""
    run = run_program([find_compiler(), *FLAGS, "-o", exe, source], "", COMPILE_TIMEOUT,
                      cwd=Path(source).parent, cancelled=cancelled, merge_stderr=True)
    if run.code is None:
        return "compile timed out"
    if run.code != 0:
        return "\n".join(run.out.splitlines()[:20]) or "compile failed"
    return None


def _text(value) -> str:
    return value.read_text(encoding="utf-8") if isinstance(value, Path) else value


def grade(folder, tests, time_limit, *, show_input=False, cancelled=lambda: False) -> Result:
    """Compile folder/sol.cpp and run it on each test, stopping at the first failure."""
    folder = Path(folder)
    source = folder / "sol.cpp"
    if not source.exists():
        raise GraderError(f"{source} not found")
    total = len(tests)
    exe = folder / "sol.exe"
    error = compile_source(source, exe, cancelled=cancelled)
    if error:
        return Result("CE", 0, total, error)
    for number, (given, expected) in enumerate(tests, 1):
        data = _text(given)
        run = run_program([exe], data, time_limit * 2, cwd=folder, cancelled=cancelled)
        if run.code is None:
            verdict = "TLE"
        elif run.code != 0:
            verdict = "RE"
        elif run.out.split() != _text(expected).split():
            verdict = "WA"
        else:
            continue
        detail = f"{verdict} on test {number}/{total}"
        if show_input and len(data) <= MAX_SHOWN_INPUT:
            detail += "\ninput:\n" + data
        return Result(verdict, number - 1, total, detail)
    return Result("AC", total, total, f"AC {total}/{total}")
