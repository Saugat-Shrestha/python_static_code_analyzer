"""Tests for naming convention rules (NAM001-NAM005).

Test design group 6. The traps here are the names that look like violations but
are completely normal Python: `__init__`, `_private`, `MAX_SIZE`, and single
letters like `i`.
"""

import textwrap
import unittest

from pyscan.analyzer import analyze_source
from pyscan.config import AnalyzerConfig


def names(source, rule_id):
    report = analyze_source(textwrap.dedent(source))
    return [issue.name for issue in report.issues_for(rule_id)]


class TestFunctionNames(unittest.TestCase):

    def test_camel_case_function_is_reported(self):
        # B-08, FR-08.
        self.assertEqual(names("def calculateTotal():\n    pass\n", "NAM001"),
                         ["calculateTotal"])

    def test_pascal_case_function_is_reported(self):
        self.assertEqual(names("def CalculateTotal():\n    pass\n", "NAM001"),
                         ["CalculateTotal"])

    def test_snake_case_function_is_clean(self):
        self.assertEqual(names("def calculate_total():\n    pass\n", "NAM001"), [])

    def test_dunder_method_is_clean(self):
        # Flagging __init__ would fire on nearly every class ever written.
        source = """
            class Account:
                def __init__(self):
                    pass
        """
        self.assertEqual(names(source, "NAM001"), [])

    def test_private_function_is_clean(self):
        self.assertEqual(names("def _helper():\n    pass\n", "NAM001"), [])

    def test_single_letter_function_is_clean(self):
        self.assertEqual(names("def f():\n    pass\n", "NAM001"), [])

    def test_method_is_reported_with_its_qualified_name(self):
        source = """
            class Account:
                def getBalance(self):
                    pass
        """
        report = analyze_source(textwrap.dedent(source))
        issue = report.issues_for("NAM001")[0]
        self.assertEqual(issue.name, "getBalance")
        self.assertIn("Account.getBalance", issue.message)
        self.assertEqual(issue.line, 3)

    def test_async_function_is_checked(self):
        self.assertEqual(names("async def fetchData():\n    pass\n", "NAM001"),
                         ["fetchData"])


class TestClassNames(unittest.TestCase):

    def test_snake_case_class_is_reported(self):
        # B-09, FR-09.
        self.assertEqual(names("class my_class:\n    pass\n", "NAM003"), ["my_class"])

    def test_pascal_case_class_is_clean(self):
        self.assertEqual(names("class MyClass:\n    pass\n", "NAM003"), [])

    def test_acronym_class_name_is_clean(self):
        # HTTPServer is normal Python, even though it is all caps at the front.
        self.assertEqual(names("class HTTPServer:\n    pass\n", "NAM003"), [])

    def test_underscore_in_class_name_is_reported(self):
        self.assertEqual(names("class Foo_Bar:\n    pass\n", "NAM003"), ["Foo_Bar"])

    def test_lowercase_class_is_reported(self):
        self.assertEqual(names("class account:\n    pass\n", "NAM003"), ["account"])


class TestVariableNames(unittest.TestCase):

    def test_camel_case_variable_is_reported(self):
        source = """
            def run():
                userName = "a"
                return userName
        """
        self.assertEqual(names(source, "NAM002"), ["userName"])

    def test_snake_case_variable_is_clean(self):
        source = """
            def run():
                user_name = "a"
                return user_name
        """
        self.assertEqual(names(source, "NAM002"), [])

    def test_upper_case_constant_is_clean(self):
        # MAX_SIZE is not snake_case, but it is the accepted way to write a
        # constant, so it must not be reported.
        self.assertEqual(names("MAX_SIZE = 10\n", "NAM002"), [])

    def test_single_letter_variable_is_clean(self):
        # BC-09.
        source = """
            def run():
                i = 0
                return i
        """
        self.assertEqual(names(source, "NAM002"), [])

    def test_annotated_variable_is_checked(self):
        source = """
            def run():
                userName: str = "a"
                return userName
        """
        self.assertEqual(names(source, "NAM002"), ["userName"])

    def test_module_level_variable_is_checked(self):
        self.assertEqual(names("myGlobal = 1\n", "NAM002"), ["myGlobal"])

    def test_the_same_bad_name_is_reported_once_per_scope(self):
        source = """
            def run():
                badName = 1
                badName = 2
                return badName
        """
        report = analyze_source(textwrap.dedent(source))
        found = report.issues_for("NAM002")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 3)

    def test_the_same_bad_name_in_two_scopes_is_reported_twice(self):
        source = """
            def one():
                badName = 1
                return badName

            def two():
                badName = 2
                return badName
        """
        self.assertEqual(names(source, "NAM002"), ["badName", "badName"])


class TestArgumentNames(unittest.TestCase):

    def test_camel_case_argument_is_reported(self):
        self.assertEqual(names("def run(userName):\n    pass\n", "NAM004"), ["userName"])

    def test_snake_case_argument_is_clean(self):
        self.assertEqual(names("def run(user_name):\n    pass\n", "NAM004"), [])

    def test_self_and_cls_are_clean(self):
        source = """
            class Account:
                def method(self):
                    pass

                @classmethod
                def build(cls):
                    pass
        """
        self.assertEqual(names(source, "NAM004"), [])

    def test_keyword_and_star_arguments_are_checked(self):
        self.assertEqual(
            names("def run(*badArgs, **badKwargs):\n    pass\n", "NAM004"),
            ["badArgs", "badKwargs"],
        )


class TestBuiltinShadowing(unittest.TestCase):

    def test_variable_shadowing_a_builtin_is_reported(self):
        # B-10, FR-10.
        source = """
            def run():
                list = [1]
                return list
        """
        self.assertEqual(names(source, "NAM005"), ["list"])

    def test_function_shadowing_a_builtin_is_reported(self):
        self.assertEqual(names("def id():\n    pass\n", "NAM005"), ["id"])

    def test_argument_shadowing_a_builtin_is_reported(self):
        self.assertEqual(names("def run(type):\n    pass\n", "NAM005"), ["type"])

    def test_similar_name_that_is_not_a_builtin_is_clean(self):
        source = """
            def run():
                my_list = [1]
                return my_list
        """
        self.assertEqual(names(source, "NAM005"), [])

    def test_dunder_names_are_not_treated_as_builtins(self):
        # __name__ and friends live in builtins-adjacent space; flagging them
        # would be wrong, and they are excluded by the leading underscore.
        source = """
            class Account:
                def __init__(self):
                    pass
        """
        self.assertEqual(names(source, "NAM005"), [])

    def test_shadowing_message_names_the_builtin(self):
        report = analyze_source("def run(type):\n    pass\n")
        self.assertIn("type", report.issues_for("NAM005")[0].message)


class TestNamingCanBeDisabled(unittest.TestCase):

    def test_disabling_a_naming_rule_removes_only_that_rule(self):
        source = textwrap.dedent("""
            def calculateTotal(userName):
                pass
        """)
        config = AnalyzerConfig(disabled_rules=frozenset({"NAM001"}))
        report = analyze_source(source, config)
        self.assertEqual(report.issues_for("NAM001"), ())
        self.assertEqual(len(report.issues_for("NAM004")), 1)


if __name__ == "__main__":
    unittest.main()
