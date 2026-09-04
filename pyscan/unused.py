"""Unused local variables (UNU001) and unused imports (UNU002).

This checker is deliberately conservative. Reporting a variable that is actually
in use is far more damaging than missing one, because it teaches people to
ignore the tool. So only plain `name = value` assignments are considered:
loop targets, `with ... as` targets and tuple unpacking are left alone, since
those names are often forced on you by the syntax rather than chosen.
"""

import ast

from pyscan.astutils import (
    iter_functions,
    own_scope_nodes,
    parameter_names,
    plain_assignments,
)
from pyscan.models import Issue


def check(context):
    issues = _unused_locals(context.tree)
    issues.extend(_unused_imports(context.tree))
    return issues


def _unused_locals(tree):
    issues = []
    for qualified_name, function_node in iter_functions(tree):
        assigned = plain_assignments(function_node)
        if not assigned:
            continue

        ignored = parameter_names(function_node) | _declared_elsewhere(function_node)
        read = _names_read_anywhere(function_node)

        for name, line in sorted(assigned.items(), key=lambda item: item[1]):
            if name in read or name in ignored or name.startswith("_"):
                continue
            issues.append(
                Issue(
                    rule_id="UNU001",
                    line=line,
                    name=name,
                    message=(
                        "variable '%s' is assigned in '%s' but never used"
                        % (name, qualified_name)
                    ),
                )
            )
    return issues


def _declared_elsewhere(function_node):
    """Names declared `global` or `nonlocal`, which belong to an outer scope."""
    declared = set()
    for node in own_scope_nodes(function_node):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
    return declared


def _names_read_anywhere(function_node):
    """Every name read inside the function, including inside nested functions.

    Nested functions are included on purpose: a closure reading an outer
    variable is a genuine use of it.
    """
    read = set()
    for node in ast.walk(function_node):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
            read.add(node.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            # `x += 1` stores into x but reads it first.
            read.add(node.target.id)
    return read


def _unused_imports(tree):
    imported = _imported_names(tree)
    if not imported:
        return []

    used = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store)
    }
    used |= _exported_names(tree)

    issues = []
    for name, line in sorted(imported.items(), key=lambda item: (item[1], item[0])):
        if name in used:
            continue
        issues.append(
            Issue(
                rule_id="UNU002",
                line=line,
                name=name,
                message="import '%s' is never used" % name,
            )
        )
    return issues


def _exported_names(tree):
    """Names listed in a literal `__all__`, which are deliberate re-exports.

    A package's `__init__.py` usually imports things purely so that other code
    can get at them, and `__all__` is how you say so. If `__all__` is built by
    code rather than written out as a literal we cannot read it, so we quietly
    give up rather than guess.
    """
    exported = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            continue
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                exported.add(element.value)
    return exported


def _imported_names(tree):
    """Map each name an import binds to the line it was bound on.

    For `import a.b.c` the name that actually enters the namespace is `a`, and
    for any aliased import it is the alias, not the original name.
    """
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                imported.setdefault(bound, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    # A star import could bring in anything, so stay quiet.
                    continue
                imported.setdefault(alias.asname or alias.name, node.lineno)
    return imported
