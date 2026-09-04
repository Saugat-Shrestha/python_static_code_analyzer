"""Tests for the public API, ordering, configuration and error handling.

Test design groups 8 and 9.
"""

import os
import tempfile
import textwrap
import time
import unittest

import pyscan
from pyscan.analyzer import analyze_file, analyze_source
from pyscan.config import ALL_RULES, AnalyzerConfig
from pyscan.errors import (
    AnalyzerError,
    ConfigurationError,
    InvalidSourceError,
    SourceFileError,
    SourceParseError,
)
from pyscan.models import AnalysisReport

MESSY_SOURCE = textwrap.dedent("""
    import os

    def calculateTotal(userName):
        unusedValue = 1
        return userName
""")


class TestPublicInterface(unittest.TestCase):

    def test_package_exports_the_main_entry_points(self):
        self.assertTrue(hasattr(pyscan, "analyze_source"))
        self.assertTrue(hasattr(pyscan, "analyze_file"))

    def test_analyze_source_returns_a_report(self):
        self.assertIsInstance(analyze_source("x = 1\n"), AnalysisReport)

    def test_clean_source_produces_no_issues(self):
        source = """
            def add(first, second):
                return first + second
        """
        report = analyze_source(textwrap.dedent(source))
        self.assertEqual(report.issues, ())
        self.assertFalse(report.has_issues)

    def test_messy_source_produces_issues(self):
        report = analyze_source(MESSY_SOURCE)
        self.assertTrue(report.has_issues)

    def test_issues_for_returns_only_the_requested_rule(self):
        report = analyze_source(MESSY_SOURCE)
        for issue in report.issues_for("NAM001"):
            self.assertEqual(issue.rule_id, "NAM001")

    def test_issues_for_an_unmatched_rule_is_empty(self):
        self.assertEqual(analyze_source("x = 1\n").issues_for("CPX001"), ())


class TestOrderingAndDeterminism(unittest.TestCase):

    def test_issues_are_sorted_by_line_number(self):
        # B-12.
        report = analyze_source(MESSY_SOURCE)
        lines = [issue.line for issue in report.issues]
        self.assertEqual(lines, sorted(lines))

    def test_issues_on_the_same_line_are_sorted_by_rule_id(self):
        # `def calculateTotal(userName)` breaks NAM001 and NAM004 on one line.
        report = analyze_source("def calculateTotal(userName):\n    pass\n")
        same_line = [i.rule_id for i in report.issues if i.line == 1]
        self.assertEqual(same_line, sorted(same_line))
        self.assertIn("NAM001", same_line)
        self.assertIn("NAM004", same_line)

    def test_the_same_input_always_gives_the_same_report(self):
        # NFR-02. Sets and dicts are used inside the duplicate checker, and
        # their iteration order must never leak into the output.
        first = analyze_source(MESSY_SOURCE)
        second = analyze_source(MESSY_SOURCE)
        self.assertEqual(first.issues, second.issues)
        self.assertEqual(first.metrics, second.metrics)


class TestConfiguration(unittest.TestCase):

    def test_disabling_a_rule_removes_only_that_rule(self):
        # B-15.
        full = analyze_source(MESSY_SOURCE)
        self.assertTrue(full.issues_for("NAM001"))

        config = AnalyzerConfig(disabled_rules=frozenset({"NAM001", "NAM002"}))
        limited = analyze_source(MESSY_SOURCE, config)
        self.assertEqual(limited.issues_for("NAM001"), ())
        self.assertEqual(limited.issues_for("NAM002"), ())
        self.assertTrue(limited.issues_for("UNU002"))

    def test_disabled_rules_accepts_a_plain_list(self):
        config = AnalyzerConfig(disabled_rules=["NAM001"])
        self.assertFalse(config.is_enabled("NAM001"))
        self.assertTrue(config.is_enabled("NAM002"))

    def test_default_config_is_used_when_none_is_given(self):
        self.assertEqual(analyze_source("x = 1\n").issues, ())

    def test_negative_complexity_threshold_is_rejected(self):
        # IN-05.
        with self.assertRaises(ConfigurationError):
            AnalyzerConfig(max_complexity=-1)

    def test_non_integer_complexity_threshold_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            AnalyzerConfig(max_complexity="ten")

    def test_duplicate_minimum_below_one_is_rejected(self):
        # IN-06.
        with self.assertRaises(ConfigurationError):
            AnalyzerConfig(min_duplicate_statements=0)

    def test_non_integer_duplicate_minimum_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            AnalyzerConfig(min_duplicate_statements="four")

    def test_boolean_is_not_accepted_as_an_integer_threshold(self):
        # True is an int in Python, but "--max-complexity True" is a mistake.
        with self.assertRaises(ConfigurationError):
            AnalyzerConfig(max_complexity=True)

    def test_unknown_rule_id_is_rejected_and_named(self):
        # IN-07.
        with self.assertRaises(ConfigurationError) as caught:
            AnalyzerConfig(disabled_rules=frozenset({"NOPE123"}))
        self.assertIn("NOPE123", str(caught.exception))


class TestInvalidSource(unittest.TestCase):

    def test_syntax_error_raises_source_parse_error_with_a_line(self):
        # IN-01.
        with self.assertRaises(SourceParseError) as caught:
            analyze_source("def broken(:\n    pass\n")
        self.assertEqual(caught.exception.line, 1)

    def test_syntax_error_message_is_useful(self):
        with self.assertRaises(SourceParseError) as caught:
            analyze_source("def broken(:\n    pass\n")
        self.assertIn("line", str(caught.exception).lower())

    def test_non_string_source_raises_invalid_source_error(self):
        # IN-02.
        for bad in (42, None, ["x = 1"], b"x = 1"):
            with self.subTest(value=bad):
                with self.assertRaises(InvalidSourceError):
                    analyze_source(bad)

    def test_null_byte_raises_source_parse_error(self):
        # IN-08.
        with self.assertRaises(SourceParseError):
            analyze_source("x = 1\x00\n")

    def test_empty_source_is_valid_not_an_error(self):
        # BC-05. An empty file is legal Python and must not raise.
        report = analyze_source("")
        self.assertEqual(report.issues, ())
        self.assertEqual(report.metrics.total_lines, 0)

    def test_every_error_type_inherits_from_analyzer_error(self):
        for error_type in (
            InvalidSourceError,
            SourceParseError,
            SourceFileError,
            ConfigurationError,
        ):
            with self.subTest(error=error_type.__name__):
                self.assertTrue(issubclass(error_type, AnalyzerError))


class TestNonFunctionalGuarantees(unittest.TestCase):
    """The promises that are not about any single rule: FR-12, NFR-01, NFR-05, NFR-08."""

    def test_analysing_code_never_executes_it(self):
        # NFR-01. The whole point of static analysis is that it is safe to run
        # against a file you do not trust. If this ever fails, the tool is
        # dangerous rather than just wrong.
        with tempfile.TemporaryDirectory() as directory:
            marker = os.path.join(directory, "side_effect.txt")
            analyze_source("open(%r, 'w').write('executed')\n" % marker)
            self.assertFalse(os.path.exists(marker))

    def test_code_that_would_crash_if_run_analyses_normally(self):
        # NFR-01 again, from the other direction.
        report = analyze_source("x = 1 / 0\nraise SystemExit(1)\n")
        self.assertEqual(report.metrics.code_lines, 2)

    def test_every_issue_carries_the_documented_fields(self):
        # FR-12. Every issue must have a known rule id, a real line number, a
        # non-empty message and a severity.
        report = analyze_source(MESSY_SOURCE)
        self.assertTrue(report.issues)
        for issue in report.issues:
            with self.subTest(rule=issue.rule_id, line=issue.line):
                self.assertIn(issue.rule_id, ALL_RULES)
                self.assertGreaterEqual(issue.line, 1)
                self.assertTrue(issue.message.strip())
                self.assertEqual(issue.severity, "warning")

    def test_messages_name_the_specific_thing_that_is_wrong(self):
        # NFR-08. "variable 'total' is never used" is actionable;
        # "unused variable" on its own is not.
        for issue in analyze_source(MESSY_SOURCE).issues:
            if issue.name is not None:
                with self.subTest(rule=issue.rule_id):
                    self.assertIn(issue.name, issue.message)

    def test_a_thousand_line_file_is_analysed_in_well_under_a_second(self):
        # NFR-05. This test is the reason the duplicate checker was rewritten:
        # the first version took 1.04 s and 1.26 GB on this exact input, because
        # it stored the text of every block of every length.
        source = "\n".join(
            "def function_%d(value):\n    total = value + %d\n    return total\n" % (index, index)
            for index in range(251)
        )
        self.assertGreaterEqual(len(source.splitlines()), 1000)

        started = time.perf_counter()
        analyze_source(source)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0, "1000 lines took %.3f seconds" % elapsed)


class TestAnalyzeFile(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def write(self, name, text):
        path = os.path.join(self.directory.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_reads_and_analyses_a_real_file(self):
        path = self.write("messy.py", MESSY_SOURCE)
        report = analyze_file(path)
        self.assertTrue(report.has_issues)
        self.assertTrue(report.issues_for("NAM001"))

    def test_metrics_come_from_the_file_contents(self):
        path = self.write("small.py", "x = 1\n\n# note\n")
        self.assertEqual(analyze_file(path).metrics.total_lines, 3)

    def test_missing_file_raises_source_file_error(self):
        # IN-03.
        missing = os.path.join(self.directory.name, "nope.py")
        with self.assertRaises(SourceFileError):
            analyze_file(missing)

    def test_directory_path_raises_source_file_error(self):
        # IN-04.
        with self.assertRaises(SourceFileError):
            analyze_file(self.directory.name)

    def test_error_message_includes_the_path(self):
        missing = os.path.join(self.directory.name, "nope.py")
        with self.assertRaises(SourceFileError) as caught:
            analyze_file(missing)
        self.assertIn("nope.py", str(caught.exception))

    def test_syntax_error_in_a_file_still_raises_parse_error(self):
        path = self.write("broken.py", "def broken(:\n")
        with self.assertRaises(SourceParseError):
            analyze_file(path)

    def test_file_that_is_not_utf8_raises_source_file_error(self):
        path = os.path.join(self.directory.name, "latin.py")
        with open(path, "wb") as handle:
            handle.write(b"# caf\xe9\nx = 1\n")
        with self.assertRaises(SourceFileError):
            analyze_file(path)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "running as root, permissions are not enforced")
    def test_unreadable_file_raises_source_file_error(self):
        path = self.write("secret.py", "x = 1\n")
        os.chmod(path, 0o000)
        self.addCleanup(os.chmod, path, 0o600)
        with self.assertRaises(SourceFileError):
            analyze_file(path)


if __name__ == "__main__":
    unittest.main()
