"""Tests for the code metrics (test design group 7).

Metrics are pure arithmetic, so they can be tested exhaustively and cheaply.
The empty-file cases matter most: an average is a division, and a file with no
functions divides by zero if nobody thought about it.
"""

import textwrap
import unittest

from pyscan.analyzer import analyze_source

MIXED_SOURCE = "\n".join([
    "# module comment",        # 1 comment
    "",                        # 2 blank
    "import os",               # 3 code
    "",                        # 4 blank
    "def run():",              # 5 code
    "    # inner comment",     # 6 comment
    "    return os  # trailing comment",  # 7 code
    "",                        # 8 blank
    "# final comment",         # 9 comment
])


def metrics(source):
    return analyze_source(textwrap.dedent(source)).metrics


class TestLineCounts(unittest.TestCase):

    def test_lines_are_split_into_code_comment_and_blank(self):
        # B-11.
        result = metrics(MIXED_SOURCE)
        self.assertEqual(result.total_lines, 9)
        self.assertEqual(result.blank_lines, 3)
        self.assertEqual(result.comment_lines, 3)
        self.assertEqual(result.code_lines, 3)

    def test_the_three_counts_add_up_to_the_total(self):
        result = metrics(MIXED_SOURCE)
        self.assertEqual(
            result.code_lines + result.comment_lines + result.blank_lines,
            result.total_lines,
        )

    def test_a_trailing_comment_counts_as_code_only(self):
        result = metrics("x = 1  # set x\n")
        self.assertEqual(result.code_lines, 1)
        self.assertEqual(result.comment_lines, 0)

    def test_whitespace_only_line_counts_as_blank(self):
        result = metrics("x = 1\n   \n")
        self.assertEqual(result.blank_lines, 1)

    def test_indented_comment_counts_as_a_comment(self):
        result = metrics("def run():\n    # note\n    pass\n")
        self.assertEqual(result.comment_lines, 1)

    def test_missing_trailing_newline_still_counts_correctly(self):
        # BC-07.
        self.assertEqual(metrics("x = 1\ny = 2").total_lines, 2)

    def test_empty_source_has_zero_lines(self):
        # BC-05.
        result = metrics("")
        self.assertEqual(result.total_lines, 0)
        self.assertEqual(result.code_lines, 0)

    def test_file_of_only_comments_has_no_code_lines(self):
        # BC-06.
        result = metrics("# one\n# two\n")
        self.assertEqual(result.code_lines, 0)
        self.assertEqual(result.comment_lines, 2)


class TestStructureCounts(unittest.TestCase):

    def test_functions_and_classes_are_counted(self):
        source = """
            class Account:
                def deposit(self):
                    pass

                def withdraw(self):
                    pass

            def helper():
                pass
        """
        result = metrics(source)
        self.assertEqual(result.class_count, 1)
        self.assertEqual(result.function_count, 3)

    def test_nested_functions_are_counted(self):
        source = """
            def outer():
                def inner():
                    pass
                return inner
        """
        self.assertEqual(metrics(source).function_count, 2)

    def test_a_file_with_no_functions_counts_zero(self):
        self.assertEqual(metrics("x = 1\n").function_count, 0)


class TestComplexityMetrics(unittest.TestCase):

    def test_average_and_maximum_complexity(self):
        source = """
            def simple():
                pass

            def branchy(flag):
                if flag:
                    return 1
                return 0
        """
        result = metrics(source)
        self.assertEqual(result.max_complexity, 2)
        self.assertEqual(result.average_complexity, 1.5)

    def test_empty_file_does_not_divide_by_zero(self):
        # BC-12. The obvious implementation of an average crashes here.
        result = metrics("")
        self.assertEqual(result.average_complexity, 0.0)
        self.assertEqual(result.max_complexity, 0)

    def test_file_with_no_functions_does_not_divide_by_zero(self):
        result = metrics("x = 1\ny = 2\n")
        self.assertEqual(result.average_complexity, 0.0)
        self.assertEqual(result.max_complexity, 0)

    def test_average_is_rounded_to_two_decimals(self):
        source = """
            def a():
                pass

            def b():
                pass

            def c(flag):
                if flag:
                    return 1
                return 0
        """
        # (1 + 1 + 2) / 3 = 1.333...
        self.assertEqual(metrics(source).average_complexity, 1.33)


class TestCommentRatio(unittest.TestCase):

    def test_ratio_is_comments_over_comments_plus_code(self):
        result = metrics("# one\nx = 1\n")
        self.assertEqual(result.comment_ratio, 0.5)

    def test_ratio_is_zero_for_an_empty_file(self):
        self.assertEqual(metrics("").comment_ratio, 0.0)

    def test_ratio_ignores_blank_lines(self):
        result = metrics("# one\n\n\n\nx = 1\n")
        self.assertEqual(result.comment_ratio, 0.5)

    def test_ratio_is_one_when_the_file_is_all_comments(self):
        self.assertEqual(metrics("# one\n# two\n").comment_ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
