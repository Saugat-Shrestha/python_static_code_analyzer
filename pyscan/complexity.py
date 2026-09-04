"""Cyclomatic complexity (rule CPX001).

Complexity starts at 1 and gains 1 for every decision point in the function
body. An `else` is deliberately not counted: it is the path taken when no
decision succeeded, not a decision of its own.
"""

import ast
from dataclasses import dataclass

from pyscan.astutils import iter_functions, own_scope_nodes
from pyscan.models import Issue

LOOP_NODES = (ast.For, ast.AsyncFor, ast.While)
SIMPLE_DECISIONS = (ast.If, ast.IfExp, ast.Assert, ast.ExceptHandler)


@dataclass(frozen=True)
class FunctionComplexity:
    """The complexity score of one function, method or nested function."""

    name: str
    line: int
    complexity: int


def function_complexities(tree):
    """Score every function in the tree, sorted by line number."""
    return [
        FunctionComplexity(name, node.lineno, _score(node))
        for name, node in iter_functions(tree)
    ]


def check(context):
    """Report functions whose complexity exceeds the configured threshold."""
    limit = context.config.max_complexity
    issues = []
    for result in function_complexities(context.tree):
        if result.complexity > limit:
            issues.append(
                Issue(
                    rule_id="CPX001",
                    line=result.line,
                    name=result.name,
                    message=(
                        "function '%s' has a cyclomatic complexity of %d, "
                        "which is above the limit of %d"
                        % (result.name, result.complexity, limit)
                    ),
                )
            )
    return issues


def _score(function_node):
    return 1 + sum(_decision_points(node) for node in own_scope_nodes(function_node))


def _decision_points(node):
    if isinstance(node, SIMPLE_DECISIONS) or isinstance(node, LOOP_NODES):
        return 1
    if isinstance(node, ast.BoolOp):
        # "a and b" is one decision, "a and b and c" is two.
        return len(node.values) - 1
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    return 0
