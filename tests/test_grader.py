from pathlib import Path
import tempfile
import unittest

import grader

try:
    grader.find_compiler()
    HAVE_GXX = True
except grader.GraderError:
    HAVE_GXX = False

ECHO_SUM = """#include <bits/stdc++.h>
int main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<"\\n";}"""
TESTS = [("1 2\n", "3\n"), ("5 5\n", "10\n"), ("7 8\n", "15")]


@unittest.skipUnless(HAVE_GXX, "g++ not found")
class GraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def judge(self, source, tests=TESTS, time_limit=1.0, **kw):
        (self.folder / "sol.cpp").write_text(source, encoding="utf-8")
        return grader.grade(self.folder, tests, time_limit, **kw)

    def test_correct_solution_is_accepted(self):
        result = self.judge(ECHO_SUM)
        self.assertEqual(result, grader.Result("AC", 3, 3, "AC 3/3"))

    def test_first_failing_test_is_reported(self):
        wrong_on_five = ECHO_SUM.replace("a+b", "(a==5?0:a+b)")
        result = self.judge(wrong_on_five)
        self.assertEqual((result.verdict, result.passed), ("WA", 1))
        self.assertTrue(result.detail.startswith("WA on test 2/3"))

    def test_main_problem_hides_the_failing_input(self):
        wrong = ECHO_SUM.replace("a+b", "a-b")
        self.assertNotIn("1 2", self.judge(wrong).detail)
        self.assertIn("1 2", self.judge(wrong, show_input=True).detail)

    def test_infinite_loop_is_time_limit_exceeded(self):
        result = self.judge("int main(){volatile int x=0;while(true){x++;}}", time_limit=0.2)
        self.assertEqual(result.verdict, "TLE")

    def test_nonzero_exit_is_runtime_error(self):
        self.assertEqual(self.judge("int main(){return 1;}").verdict, "RE")

    def test_syntax_error_is_compile_error(self):
        result = self.judge("int main( {")
        self.assertEqual(result.verdict, "CE")
        self.assertTrue(result.detail)

    def test_tests_may_be_files(self):
        given, expected = self.folder / "01.in", self.folder / "01.out"
        given.write_text("2 2\n", encoding="utf-8")
        expected.write_text("4\n", encoding="utf-8")
        self.assertEqual(self.judge(ECHO_SUM, tests=[(given, expected)]).verdict, "AC")

    def test_deep_recursion_does_not_crash(self):
        deep = """#include <bits/stdc++.h>
int f(int n){return n==0?0:1+f(n-1);}
int main(){std::cout<<f(1000000)<<"\\n";}"""
        self.assertEqual(self.judge(deep, tests=[("", "1000000")]).verdict, "AC")

    def test_cancel_stops_grading(self):
        with self.assertRaises(grader.GraderError):
            self.judge(ECHO_SUM, cancelled=lambda: True)


class MissingSourceTests(unittest.TestCase):
    def test_missing_sol_cpp_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(grader.GraderError):
                grader.grade(Path(d), TESTS, 1.0)
