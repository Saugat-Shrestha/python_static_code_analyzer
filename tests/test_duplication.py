"""Tests for duplicate code detection (DUP001).

Test design group 5. The interesting part of this checker is not finding the
duplicates, it is reporting each one exactly once. Overlapping sliding windows
mean a single copy-paste can easily produce half a dozen warnings.
"""

import textwrap
import unittest

from pyscan.analyzer import analyze_source
from pyscan.config import AnalyzerConfig


def duplicates(source, min_statements=4):
    report = analyze_source(
        textwrap.dedent(source),
        AnalyzerConfig(min_duplicate_statements=min_statements),
    )
    return report.issues_for("DUP001")


class TestDuplicateDetection(unittest.TestCase):

    def test_two_identical_blocks_are_reported_once(self):
        source = """
            def first(data):
                total = 0
                count = 0
                total = total + 1
                count = count + 1
                return total

            def second(data):
                total = 0
                count = 0
                total = total + 1
                count = count + 1
                return total
        """
        found = duplicates(source)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 3)
        self.assertEqual(found[0].related_lines, (10,))

    def test_blocks_differing_only_in_variable_names_are_still_duplicates(self):
        # B-07, FR-07, A-06: renaming the variables is the most common way copy-pasted code
        # hides from an exact-text comparison.
        source = """
            def first(data):
                total = 0
                count = 0
                total = total + 1
                count = count + 1

            def second(data):
                amount = 0
                tally = 0
                amount = amount + 1
                tally = tally + 1
        """
        self.assertEqual(len(duplicates(source)), 1)

    def test_blocks_with_different_structure_are_not_duplicates(self):
        source = """
            def first(data):
                total = 0
                count = 0
                total = total + 1
                count = count + 1

            def second(data):
                for item in data:
                    print(item)
                return len(data)
        """
        self.assertEqual(duplicates(source), ())

    def test_different_method_names_are_not_duplicates(self):
        # Only variable names are normalised. `append` and `remove` are
        # different operations and must not be treated as the same code.
        source = """
            def first(data):
                data.append(1)
                data.append(2)
                data.append(3)
                data.append(4)

            def second(data):
                data.remove(1)
                data.remove(2)
                data.remove(3)
                data.remove(4)
        """
        self.assertEqual(duplicates(source), ())

    def test_three_copies_produce_one_issue_listing_all_locations(self):
        block = """
            def name(data):
                total = 0
                count = 0
                total = total + 1
                count = count + 1
        """
        source = textwrap.dedent(block).replace("name", "first")
        source += textwrap.dedent(block).replace("name", "second")
        source += textwrap.dedent(block).replace("name", "third")
        report = analyze_source(source, AnalyzerConfig(min_duplicate_statements=4))
        found = report.issues_for("DUP001")
        self.assertEqual(len(found), 1)
        self.assertEqual(len(found[0].related_lines), 2)

    def test_a_longer_duplicate_is_reported_once_not_once_per_window(self):
        # Six duplicated statements with a minimum of four would match at three
        # different window offsets. Only the longest, whole block should appear.
        body = "\n".join("    value_%d = %d" % (i, i) for i in range(6))
        source = "def first(data):\n%s\n\ndef second(data):\n%s\n" % (body, body)
        found = duplicates(source)
        self.assertEqual(len(found), 1)
        self.assertIn("6", found[0].message)


class TestDuplicateBoundaries(unittest.TestCase):

    @staticmethod
    def source_with_block_of(size):
        body = "\n".join("    value_%d = %d" % (i, i) for i in range(size))
        return "def first(data):\n%s\n\ndef second(data):\n%s\n" % (body, body)

    def test_block_exactly_at_the_minimum_is_reported(self):
        # BC-04.
        self.assertEqual(len(duplicates(self.source_with_block_of(4), 4)), 1)

    def test_block_one_statement_below_the_minimum_is_not_reported(self):
        # BC-03.
        self.assertEqual(duplicates(self.source_with_block_of(3), 4), ())

    def test_minimum_of_one_is_allowed(self):
        self.assertEqual(len(duplicates(self.source_with_block_of(1), 1)), 1)

    def test_repeated_single_statement_is_not_reported_at_default_minimum(self):
        # BC-10. Five copies of one statement cannot make a non-overlapping
        # pair of four-statement blocks.
        source = "x = 1\n" * 5
        self.assertEqual(duplicates(source, 4), ())

    def test_overlapping_occurrences_do_not_count_as_two(self):
        # a, b, a, b, a. At a minimum of three the only matching pair is
        # (a,b,a) at index 0 and (a,b,a) at index 2, and they share the middle
        # `a`. One block cannot be a duplicate of itself, so nothing is reported.
        source = "a = 1\nb = 2\na = 1\nb = 2\na = 1\n"
        self.assertEqual(duplicates(source, 3), ())

    def test_the_same_source_does_report_when_the_pair_stops_overlapping(self):
        # Same input, minimum of two: (a,b) at lines 1 and 3 do not share a
        # statement, so this one is real duplication.
        source = "a = 1\nb = 2\na = 1\nb = 2\na = 1\n"
        found = duplicates(source, 2)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 1)
        self.assertEqual(found[0].related_lines, (3,))

    def test_empty_source_produces_nothing(self):
        self.assertEqual(duplicates(""), ())


class TestDuplicateReporting(unittest.TestCase):

    # source_with_block_of(4) lays out as:
    #   1 def first(data):     2-5 the four statements     6 blank
    #   7 def second(data):    8-11 the same four statements

    def test_message_mentions_the_block_size_and_the_other_line(self):
        source = TestDuplicateBoundaries.source_with_block_of(4)
        message = duplicates(source, 4)[0].message
        self.assertIn("4 statements", message)
        self.assertIn("line 8", message)

    def test_issue_is_reported_at_the_first_occurrence(self):
        source = TestDuplicateBoundaries.source_with_block_of(4)
        found = duplicates(source, 4)[0]
        self.assertEqual(found.line, 2)
        self.assertEqual(found.related_lines, (8,))

    def test_duplicates_inside_a_single_function_are_found(self):
        source = """
            def process(data):
                total = 0
                count = 0
                total = total + 1
                count = count + 1
                print(data)
                total = 0
                count = 0
                total = total + 1
                count = count + 1
        """
        self.assertEqual(len(duplicates(source)), 1)


if __name__ == "__main__":
    unittest.main()
