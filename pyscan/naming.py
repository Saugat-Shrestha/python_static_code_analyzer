"""Naming convention rules (NAM001-NAM005), based on PEP 8.

The patterns are deliberately permissive about underscores. `__init__`,
`_helper` and `MAX_SIZE` are all perfectly normal Python, and a checker that
complains about them would be switched off within a day.
"""

import ast
import builtins
import re

from pyscan.astutils import iter_functions, plain_assignments
from pyscan.models import Issue

# Anything with no capital letters. Leading and trailing underscores are fine,
# which is what lets `_helper` and `__init__` through.
SNAKE_CASE = re.compile(r"^[a-z_][a-z0-9_]*$")

# The constant convention, e.g. MAX_SIZE. Allowed anywhere a variable is bound.
CONSTANT_CASE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

# Starts with a capital, no underscores inside. Allows HTTPServer.
PASCAL_CASE = re.compile(r"^_?[A-Z][a-zA-Z0-9]*$")

# `self` and `cls` are conventions, not choices the author made.
IMPLICIT_ARGUMENTS = frozenset({"self", "cls"})

BUILTIN_NAMES = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)


def check(context):
    issues = []
    issues.extend(_check_classes(context.tree))
    issues.extend(_check_functions(context.tree))
    issues.extend(_check_variables(context.tree))
    return issues


def _check_classes(tree):
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not PASCAL_CASE.match(node.name):
            issues.append(
                Issue(
                    rule_id="NAM003",
                    line=node.lineno,
                    name=node.name,
                    message="class '%s' should be named in PascalCase" % node.name,
                )
            )
        issues.extend(_shadow_issue(node.name, node.lineno, "class"))
    return issues


def _check_functions(tree):
    issues = []
    for qualified_name, node in iter_functions(tree):
        if not SNAKE_CASE.match(node.name):
            issues.append(
                Issue(
                    rule_id="NAM001",
                    line=node.lineno,
                    name=node.name,
                    message="function '%s' should be named in snake_case" % qualified_name,
                )
            )
        issues.extend(_shadow_issue(node.name, node.lineno, "function"))
        issues.extend(_check_arguments(node))
    return issues


def _check_arguments(function_node):
    issues = []
    for argument in _all_arguments(function_node):
        if argument.arg in IMPLICIT_ARGUMENTS:
            continue
        if not SNAKE_CASE.match(argument.arg):
            issues.append(
                Issue(
                    rule_id="NAM004",
                    line=argument.lineno,
                    name=argument.arg,
                    message="argument '%s' should be named in snake_case" % argument.arg,
                )
            )
        issues.extend(_shadow_issue(argument.arg, argument.lineno, "argument"))
    return issues


def _all_arguments(function_node):
    args = function_node.args
    ordered = list(args.posonlyargs) + list(args.args)
    if args.vararg is not None:
        ordered.append(args.vararg)
    ordered.extend(args.kwonlyargs)
    if args.kwarg is not None:
        ordered.append(args.kwarg)
    return ordered


def _check_variables(tree):
    """Check assignments at module level and inside each function separately.

    Scoping matters here: the same badly named variable in two functions is two
    problems for two people to fix, not one.
    """
    scopes = [tree] + [node for _, node in iter_functions(tree)]
    issues = []
    for scope in scopes:
        for name, line in sorted(plain_assignments(scope).items(), key=lambda i: i[1]):
            if not SNAKE_CASE.match(name) and not CONSTANT_CASE.match(name):
                issues.append(
                    Issue(
                        rule_id="NAM002",
                        line=line,
                        name=name,
                        message="variable '%s' should be named in snake_case" % name,
                    )
                )
            issues.extend(_shadow_issue(name, line, "variable"))
    return issues


def _shadow_issue(name, line, kind):
    if name not in BUILTIN_NAMES:
        return []
    return [
        Issue(
            rule_id="NAM005",
            line=line,
            name=name,
            message="%s '%s' shadows the Python built-in of the same name" % (kind, name),
        )
    ]
