import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bank  # noqa: E402
import grader  # noqa: E402
import make_problem  # noqa: E402

try:
    grader.find_compiler()
    HAVE_GXX = True
except grader.GraderError:
    HAVE_GXX = False

SUM = """#include <bits/stdc++.h>
int main(){int n;std::cin>>n;long long s=0;for(int i=0;i<n;i++){long long x;std::cin>>x;s+=x;}std::cout<<s<<"\\n";}"""
GEN = """import random, sys
random.seed(int(sys.argv[1]))
n = 3 if sys.argv[2] == "small" else 1000
print(n)
print(*[random.randint(1, 9) for _ in range(n)])
"""


def candidate(**overrides):
    base = {"title": "Sum Them", "slug": "sum-them", "statement": "# Sum Them\n",
            "reference_cpp": SUM, "brute_cpp": SUM, "gen_py": GEN, "time_limit": 1.0}
    return {**base, **overrides}


@unittest.skipUnless(HAVE_GXX, "g++ not found")
class VerifyTests(unittest.TestCase):
    def test_agreeing_solutions_produce_tests(self):
        with tempfile.TemporaryDirectory() as d:
            tests = make_problem.verify(candidate(), Path(d), small=5, large=1, keep_small=3)
        self.assertEqual(len(tests), 4)
        given, expected = tests[0]
        self.assertEqual(int(expected), sum(map(int, given.split()[1:])))

    def test_disagreeing_reference_is_rejected(self):
        wrong = SUM.replace("s+=x", "s+=x*(i>0)")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(make_problem.Rejected):
                make_problem.verify(candidate(reference_cpp=wrong), Path(d), small=5, large=1)

    def test_reference_that_does_not_compile_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(make_problem.Rejected):
                make_problem.verify(candidate(reference_cpp="int main( {"), Path(d), small=1, large=1)


class WriteEntryTests(unittest.TestCase):
    def test_written_entry_loads_in_the_bank(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_problem.write_entry(root, candidate(), 1, "implementation",
                                     [("3\n1 2 3\n", "6\n")])
            (entry,) = bank.load(root)
            self.assertEqual((entry.id, entry.level, len(entry.tests)),
                             ("camp1/sum-them", 1, 1))
            meta = json.loads((root / "camp1" / "sum-them" / "meta.json").read_text("utf-8"))
            self.assertEqual(meta["topic"], "implementation")

    def test_existing_slug_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_problem.write_entry(root, candidate(), 1, "implementation", [("1\n5\n", "5\n")])
            with self.assertRaises(make_problem.Rejected):
                make_problem.write_entry(root, candidate(), 1, "implementation", [("1\n5\n", "5\n")])

    def test_bad_slug_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(make_problem.Rejected):
                make_problem.write_entry(Path(d), candidate(slug="../evil"), 1,
                                         "implementation", [("1\n5\n", "5\n")])
