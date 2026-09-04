"""Tests for unused local variables (UNU001) and unused imports (UNU002).

Test design groups 3 and 4. Most of these are negative tests, because the real
risk with this checker is false positives: a linter that complains about
variables you are actually using gets switched off.
"""

import textwrap
import unittest

from pyscan.analyzer import analyze_source


def issues(source, rule_id):
    report = analyze_source(textwrap.dedent(source))
    return report.issues_for(rule_id)


def names(source, rule_id):
    return [issue.name for issue in issues(source, rule_id)]


class TestUnusedLocalVariables(unittest.TestCase):

    def test_variable_assigned_and_never_read_is_reported(self):
        # B-04, FR-05.
        source = """
            def compute():
                total = 0
                return 42
        """
        found = issues(source, "UNU001")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "total")
        self.assertEqual(found[0].line, 3)
        self.assertIn("total", found[0].message)

    def test_variable_that_is_read_later_is_not_reported(self):
        # B-05, FR-05.
        source = """
            def compute():
                total = 0
                return total
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_variable_read_inside_a_branch_is_not_reported(self):
        source = """
            def compute(flag):
                total = 0
                if flag:
                    return total
                return -1
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_variable_used_only_by_a_nested_function_is_not_reported(self):
        # A closure read is still a read.
        source = """
            def outer():
                message = "hello"
                def inner():
                    return message
                return inner
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_augmented_assignment_counts_as_a_read(self):
        source = """
            def compute(items):
                total = 0
                for item in items:
                    total += item
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_unused_parameter_is_not_reported_as_an_unused_variable(self):
        source = """
            def handle(request, context):
                return 1
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_reassigned_parameter_is_not_reported(self):
        source = """
            def handle(value):
                value = 0
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_underscore_is_never_reported(self):
        # BC-08. A leading underscore means "I know, I do not need this".
        source = """
            def compute():
                _ = expensive()
                _ignored = 1
                return 0
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_loop_variable_is_not_reported(self):
        source = """
            def repeat(times):
                for index in range(times):
                    print("hi")
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_tuple_unpacking_target_is_not_reported(self):
        # Unpacking often forces you to bind names you do not want.
        source = """
            def first(pair):
                head, tail = pair
                return head
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_with_statement_target_is_not_reported(self):
        source = """
            def touch(path):
                with open(path) as handle:
                    pass
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_global_declared_name_is_not_reported(self):
        source = """
            def configure():
                global setting
                setting = 1
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_variable_assigned_twice_and_never_read_is_reported_once(self):
        source = """
            def compute():
                total = 0
                total = 1
                return 5
        """
        found = issues(source, "UNU001")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 3)

    def test_annotated_assignment_is_checked(self):
        source = """
            def compute():
                total: int = 0
                return 42
        """
        self.assertEqual(names(source, "UNU001"), ["total"])

    def test_bare_annotation_without_a_value_is_not_an_assignment(self):
        # `total: int` declares a type but binds nothing, so there is no
        # variable sitting there unused.
        source = """
            def compute():
                total: int
                return 42
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_annotated_attribute_assignment_is_not_a_local_variable(self):
        # `self.total` is an attribute, not a local, so it is none of our business.
        source = """
            class Account:
                def __init__(self):
                    self.total: int = 0
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_star_args_and_kwargs_are_treated_as_parameters(self):
        source = """
            def collect(*items, **options):
                items = 1
                options = 2
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_module_level_variable_is_not_reported(self):
        # A-04: another module may import it, and we cannot see that from here.
        source = """
            SETTING = 1
        """
        self.assertEqual(names(source, "UNU001"), [])

    def test_each_function_is_scoped_separately(self):
        # `total` is used in one function; that must not excuse the other one.
        source = """
            def good():
                total = 1
                return total

            def bad():
                total = 1
                return 0
        """
        found = issues(source, "UNU001")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 7)

    def test_method_bodies_are_checked(self):
        source = """
            class Account:
                def withdraw(self, amount):
                    fee = 2
                    return amount
        """
        self.assertEqual(names(source, "UNU001"), ["fee"])


class TestUnusedImports(unittest.TestCase):

    def test_unused_plain_import_is_reported(self):
        # B-06, FR-06.
        source = """
            import os

            def run():
                return 1
        """
        found = issues(source, "UNU002")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "os")
        self.assertEqual(found[0].line, 2)

    def test_used_import_is_not_reported(self):
        source = """
            import os

            def run():
                return os.getcwd()
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_dotted_import_used_through_its_root_is_not_reported(self):
        source = """
            import os.path

            def run():
                return os.path.join("a", "b")
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_alias_is_tracked_under_the_alias_not_the_original(self):
        source = """
            import collections as coll

            def run():
                return coll.OrderedDict()
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_unused_alias_is_reported_using_the_alias(self):
        source = """
            import collections as coll
        """
        self.assertEqual(names(source, "UNU002"), ["coll"])

    def test_unused_from_import_is_reported(self):
        source = """
            from os import getcwd
        """
        self.assertEqual(names(source, "UNU002"), ["getcwd"])

    def test_used_from_import_with_alias_is_not_reported(self):
        source = """
            from os import getcwd as cwd

            def run():
                return cwd()
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_star_import_is_never_reported(self):
        # We cannot tell what a star import brought in, so we say nothing.
        source = """
            from os import *
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_import_used_only_as_a_decorator_is_not_reported(self):
        source = """
            import functools

            @functools.cache
            def run():
                return 1
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_import_used_only_in_a_type_annotation_is_not_reported(self):
        source = """
            import decimal

            def run(value: decimal.Decimal):
                return 1
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_names_listed_in_dunder_all_count_as_used(self):
        # Regression. Running PyScan on its own package reported every
        # re-export in __init__.py as unused. Listing a name in __all__ is the
        # standard way of saying "this is deliberately re-exported".
        source = """
            from os import getcwd

            __all__ = ["getcwd"]
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_dunder_all_written_as_a_tuple_also_counts(self):
        source = """
            from os import getcwd

            __all__ = ("getcwd",)
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_dunder_all_built_dynamically_is_ignored_without_crashing(self):
        # We cannot read a computed __all__, so fall back to normal behaviour
        # rather than guessing or blowing up.
        source = """
            from os import getcwd

            __all__ = [name for name in dir()]
        """
        self.assertEqual(names(source, "UNU002"), ["getcwd"])

    def test_non_string_entries_in_dunder_all_are_skipped(self):
        source = """
            from os import getcwd

            __all__ = ["getcwd", 123, None]
        """
        self.assertEqual(names(source, "UNU002"), [])

    def test_dunder_all_naming_something_not_imported_is_harmless(self):
        source = """
            import os

            __all__ = ["something_else"]
        """
        self.assertEqual(names(source, "UNU002"), ["os"])

    def test_several_unused_imports_are_all_reported(self):
        source = """
            import os
            import sys
            import json

            def run():
                return json.dumps({})
        """
        self.assertEqual(names(source, "UNU002"), ["os", "sys"])


if __name__ == "__main__":
    unittest.main()
