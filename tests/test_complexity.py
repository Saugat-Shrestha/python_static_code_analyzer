"""Tests for cyclomatic complexity counting and the CPX001 threshold rule.

Test design groups 1 and 2.
"""

import ast
import textwrap
import unittest

from pyscan.analyzer import analyze_source
from pyscan.complexity import function_complexities
from pyscan.config import AnalyzerConfig


def complexity_of(source, name):
    """Return the complexity of one named function in a snippet."""
    results = function_complexities(ast.parse(textwrap.dedent(source)))
    for result in results:
        if result.name == name:
            return result.complexity
    raise AssertionError("no function called %r in %r" % (name, [r.name for r in results]))


class TestComplexityCounting(unittest.TestCase):
    """Group 1: does each decision point add exactly one?"""

    def test_straight_line_function_scores_one(self):
        # B-01, FR-03.
        source = """
            def add(a, b):
                total = a + b
                return total
        """
        self.assertEqual(complexity_of(source, "add"), 1)

    def test_single_if_adds_one(self):
        # B-02, FR-03.
        source = """
            def check(value):
                if value > 0:
                    return "positive"
                return "not positive"
        """
        self.assertEqual(complexity_of(source, "check"), 2)

    def test_else_does_not_add_anything(self):
        # An else branch is the fall-through, not a decision. if/else is still 2.
        source = """
            def check(value):
                if value > 0:
                    return "positive"
                else:
                    return "not positive"
        """
        self.assertEqual(complexity_of(source, "check"), 2)

    def test_elif_adds_one_each(self):
        source = """
            def grade(mark):
                if mark >= 85:
                    return "HD"
                elif mark >= 75:
                    return "D"
                elif mark >= 65:
                    return "C"
                else:
                    return "F"
        """
        self.assertEqual(complexity_of(source, "grade"), 4)

    def test_for_loop_adds_one(self):
        source = """
            def total(items):
                result = 0
                for item in items:
                    result += item
                return result
        """
        self.assertEqual(complexity_of(source, "total"), 2)

    def test_while_loop_adds_one(self):
        source = """
            def countdown(n):
                while n > 0:
                    n -= 1
                return n
        """
        self.assertEqual(complexity_of(source, "countdown"), 2)

    def test_each_except_handler_adds_one(self):
        source = """
            def load(path):
                try:
                    return open(path).read()
                except FileNotFoundError:
                    return ""
                except PermissionError:
                    return ""
        """
        self.assertEqual(complexity_of(source, "load"), 3)

    def test_boolean_operator_counts_each_extra_operand(self):
        # "a and b and c" is two decisions, not one.
        source = """
            def valid(a, b, c):
                return a and b and c
        """
        self.assertEqual(complexity_of(source, "valid"), 3)

    def test_conditional_expression_adds_one(self):
        source = """
            def label(flag):
                return "yes" if flag else "no"
        """
        self.assertEqual(complexity_of(source, "label"), 2)

    def test_comprehension_for_and_if_each_add_one(self):
        source = """
            def evens(items):
                return [i for i in items if i % 2 == 0]
        """
        self.assertEqual(complexity_of(source, "evens"), 3)

    def test_assert_adds_one(self):
        source = """
            def divide(a, b):
                assert b != 0
                return a / b
        """
        self.assertEqual(complexity_of(source, "divide"), 2)


class TestComplexityScoping(unittest.TestCase):
    """Group 1: which code belongs to which function?"""

    def test_methods_are_reported_with_qualified_names(self):
        source = """
            class Account:
                def withdraw(self, amount):
                    if amount > 0:
                        return amount
                    return 0
        """
        self.assertEqual(complexity_of(source, "Account.withdraw"), 2)

    def test_nested_function_is_measured_separately(self):
        # The outer function should not be blamed for the inner function's branches.
        source = """
            def outer(items):
                def inner(x):
                    if x:
                        return 1
                    return 0
                return [inner(i) for i in items]
        """
        self.assertEqual(complexity_of(source, "outer.inner"), 2)
        self.assertEqual(complexity_of(source, "outer"), 2)

    def test_module_level_code_is_not_reported_as_a_function(self):
        source = """
            if True:
                x = 1
        """
        results = function_complexities(ast.parse(textwrap.dedent(source)))
        self.assertEqual(results, [])

    def test_async_function_is_measured(self):
        source = """
            async def fetch(items):
                for item in items:
                    pass
        """
        self.assertEqual(complexity_of(source, "fetch"), 2)


class TestComplexityThreshold(unittest.TestCase):
    """Group 2: the CPX001 rule, and the boundary at the threshold."""

    @staticmethod
    def build_function(branch_count):
        """Build a function whose complexity is branch_count + 1."""
        lines = ["def busy(value):"]
        for index in range(branch_count):
            lines.append("    if value == %d:" % index)
            lines.append("        return %d" % index)
        lines.append("    return -1")
        return "\n".join(lines)

    def test_complexity_equal_to_threshold_is_not_reported(self):
        # BC-01. The rule is "exceeds", so exactly 10 must stay clean.
        source = self.build_function(9)
        self.assertEqual(complexity_of(source, "busy"), 10)
        report = analyze_source(source, AnalyzerConfig(max_complexity=10))
        self.assertEqual(report.issues_for("CPX001"), ())

    def test_complexity_one_above_threshold_is_reported(self):
        # B-03, BC-02, FR-04.
        source = self.build_function(10)
        self.assertEqual(complexity_of(source, "busy"), 11)
        report = analyze_source(source, AnalyzerConfig(max_complexity=10))
        issues = report.issues_for("CPX001")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].name, "busy")

    def test_message_names_the_function_and_both_numbers(self):
        report = analyze_source(self.build_function(10), AnalyzerConfig(max_complexity=10))
        message = report.issues_for("CPX001")[0].message
        self.assertIn("busy", message)
        self.assertIn("11", message)
        self.assertIn("10", message)

    def test_issue_points_at_the_def_line(self):
        source = "\n\n" + self.build_function(10)
        report = analyze_source(source, AnalyzerConfig(max_complexity=10))
        self.assertEqual(report.issues_for("CPX001")[0].line, 3)

    def test_threshold_of_zero_reports_every_function(self):
        # BC-11. A simple function has complexity 1, which exceeds 0.
        source = """
            def a():
                pass

            def b():
                pass
        """
        report = analyze_source(textwrap.dedent(source), AnalyzerConfig(max_complexity=0))
        self.assertEqual(len(report.issues_for("CPX001")), 2)

    def test_custom_threshold_is_respected(self):
        source = self.build_function(3)  # complexity 4
        self.assertEqual(report_count(source, 3), 1)
        self.assertEqual(report_count(source, 4), 0)


def report_count(source, threshold):
    report = analyze_source(source, AnalyzerConfig(max_complexity=threshold))
    return len(report.issues_for("CPX001"))


if __name__ == "__main__":
    unittest.main()
