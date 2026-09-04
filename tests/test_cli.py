"""Tests for the command-line interface (test design group 10).

Exit codes are the important part. They are invisible when you run the tool by
hand, so if a test does not check them, nothing ever will — and a linter that
reports problems and then exits 0 would let a broken build pass.
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from pyscan.cli import EXIT_CLEAN, EXIT_ISSUES, EXIT_ERROR, main

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLEAN_SOURCE = textwrap.dedent("""
    def add(first, second):
        return first + second
""")

MESSY_SOURCE = textwrap.dedent("""
    import os

    def calculateTotal(userName):
        unusedValue = 1
        return userName
""")


class CliTestCase(unittest.TestCase):
    """Shared plumbing: a temp directory and captured output streams."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.out = io.StringIO()
        self.err = io.StringIO()

    def write(self, name, text):
        path = os.path.join(self.directory.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_cli(self, *argv):
        code = main(list(argv), stdout=self.out, stderr=self.err)
        return code, self.out.getvalue(), self.err.getvalue()


class TestExitCodes(CliTestCase):

    def test_clean_file_exits_zero(self):
        # B-13.
        path = self.write("clean.py", CLEAN_SOURCE)
        code, out, _ = self.run_cli(path)
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("no issues", out.lower())

    def test_file_with_issues_exits_one(self):
        # B-14. The whole point of the exit code contract.
        path = self.write("messy.py", MESSY_SOURCE)
        code, _, _ = self.run_cli(path)
        self.assertEqual(code, EXIT_ISSUES)

    def test_no_arguments_prints_usage_and_exits_with_an_error(self):
        # IN-09.
        code, _, err = self.run_cli()
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("usage", err.lower())

    def test_missing_file_exits_with_an_error(self):
        code, _, err = self.run_cli(os.path.join(self.directory.name, "nope.py"))
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("nope.py", err)

    def test_unparsable_file_exits_with_an_error_not_a_traceback(self):
        path = self.write("broken.py", "def broken(:\n")
        code, _, err = self.run_cli(path)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("broken.py", err)

    def test_bad_configuration_exits_with_an_error(self):
        path = self.write("clean.py", CLEAN_SOURCE)
        code, _, err = self.run_cli("--disable", "NOPE123", path)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("NOPE123", err)


class TestOutput(CliTestCase):

    def test_issue_lines_show_the_line_number_and_rule_id(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli(path)
        self.assertIn("4:NAM001", out)

    def test_issue_lines_include_the_message(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli(path)
        self.assertIn("snake_case", out)

    def test_the_file_name_is_printed(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli(path)
        self.assertIn("messy.py", out)

    def test_metrics_are_printed(self):
        path = self.write("clean.py", CLEAN_SOURCE)
        _, out, _ = self.run_cli(path)
        self.assertIn("lines", out.lower())
        self.assertIn("complexity", out.lower())

    def test_a_summary_count_is_printed(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli(path)
        self.assertIn("issue", out.lower())

    def test_quiet_mode_hides_metrics_but_keeps_issues(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli("--quiet", path)
        self.assertIn("NAM001", out)
        self.assertNotIn("blank", out.lower())


class TestOptions(CliTestCase):

    def test_max_complexity_option_is_applied(self):
        source = textwrap.dedent("""
            def branchy(flag):
                if flag:
                    return 1
                return 0
        """)
        path = self.write("branchy.py", source)

        code, _, _ = self.run_cli(path)
        self.assertEqual(code, EXIT_CLEAN)

        self.setUp()
        code, out, _ = self.run_cli("--max-complexity", "1", path)
        self.assertEqual(code, EXIT_ISSUES)
        self.assertIn("CPX001", out)

    def test_disable_option_removes_that_rule(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli("--disable", "NAM001", path)
        self.assertNotIn("NAM001", out)
        self.assertIn("UNU002", out)

    def test_disable_accepts_several_rules(self):
        path = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli("--disable", "NAM001", "--disable", "NAM002", path)
        self.assertNotIn("NAM001", out)
        self.assertNotIn("NAM002", out)

    def test_negative_max_complexity_is_rejected(self):
        path = self.write("clean.py", CLEAN_SOURCE)
        code, _, err = self.run_cli("--max-complexity", "-1", path)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("max_complexity", err)

    def test_list_rules_prints_every_rule_and_exits_clean(self):
        code, out, _ = self.run_cli("--list-rules")
        self.assertEqual(code, EXIT_CLEAN)
        for rule_id in ("CPX001", "UNU001", "DUP001", "NAM001", "NAM005"):
            self.assertIn(rule_id, out)


class TestArgparseHandling(CliTestCase):
    """argparse exits by itself; main has to turn that into a return code."""

    def test_help_exits_cleanly(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["--help"], stdout=self.out, stderr=self.err)
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("usage", buffer.getvalue().lower())

    def test_unknown_option_exits_with_an_error(self):
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = main(["--not-a-real-option"], stdout=self.out, stderr=self.err)
        self.assertEqual(code, EXIT_ERROR)

    def test_streams_default_to_stdout_and_stderr(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["--list-rules"])
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("CPX001", buffer.getvalue())


class TestRunAsAModule(CliTestCase):
    """`python -m pyscan` must actually work, not just `main()`."""

    def test_module_entry_point_reports_issues_and_exits_one(self):
        path = self.write("messy.py", MESSY_SOURCE)
        result = subprocess.run(
            [sys.executable, "-m", "pyscan", path],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, EXIT_ISSUES)
        self.assertIn("NAM001", result.stdout)

    def test_module_entry_point_exits_zero_on_clean_code(self):
        path = self.write("clean.py", CLEAN_SOURCE)
        result = subprocess.run(
            [sys.executable, "-m", "pyscan", path],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, EXIT_CLEAN)


class TestSeveralFiles(CliTestCase):

    def test_all_files_are_analysed(self):
        first = self.write("clean.py", CLEAN_SOURCE)
        second = self.write("messy.py", MESSY_SOURCE)
        _, out, _ = self.run_cli(first, second)
        self.assertIn("clean.py", out)
        self.assertIn("messy.py", out)

    def test_exit_code_is_one_if_any_file_has_issues(self):
        first = self.write("clean.py", CLEAN_SOURCE)
        second = self.write("messy.py", MESSY_SOURCE)
        code, _, _ = self.run_cli(first, second)
        self.assertEqual(code, EXIT_ISSUES)

    def test_exit_code_is_zero_only_when_every_file_is_clean(self):
        first = self.write("a.py", CLEAN_SOURCE)
        second = self.write("b.py", CLEAN_SOURCE)
        code, _, _ = self.run_cli(first, second)
        self.assertEqual(code, EXIT_CLEAN)

    def test_one_unreadable_file_stops_the_run_with_an_error(self):
        good = self.write("clean.py", CLEAN_SOURCE)
        missing = os.path.join(self.directory.name, "nope.py")
        code, _, err = self.run_cli(good, missing)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("nope.py", err)


if __name__ == "__main__":
    unittest.main()
