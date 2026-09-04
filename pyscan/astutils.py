"""Small AST helpers shared by more than one checker."""

import ast

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPE_NODES = FUNCTION_NODES + (ast.ClassDef,)


def walk_own_scope(node):
    """Yield `node` and its descendants, stopping at nested functions and classes.

    The check happens on entry rather than on the children, so passing a nested
    `def` straight in yields nothing at all.
    """
    if isinstance(node, SCOPE_NODES):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from walk_own_scope(child)


def own_scope_nodes(function_node):
    """Yield every node belonging to a function's own scope, nested defs excluded."""
    for statement in function_node.body:
        yield from walk_own_scope(statement)


def plain_assignments(scope_node):
    """Map plainly assigned names in a scope to the line of the first assignment.

    Works for a module or a function, since both keep their statements in
    `.body`. Only `name = value` and `name: T = value` count. Loop targets,
    `with ... as` targets and tuple unpacking are left out on purpose: those
    names are usually forced by the syntax rather than chosen, so treating them
    the same way produces noise.
    """
    assigned = {}
    for node in own_scope_nodes(scope_node):
        for target in _assigned_names(node):
            assigned.setdefault(target, node.lineno)
    return assigned


def _assigned_names(node):
    """The plain variable names a single statement binds, if any."""
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        # An annotated attribute (`self.total: int = 0`) is not a local.
        if isinstance(node.target, ast.Name):
            return [node.target.id]
    return []


def iter_functions(tree):
    """Return (qualified_name, node) for every function, sorted by line.

    Methods and nested functions get a dotted name (`Account.withdraw`,
    `outer.inner`) so two functions with the same short name can be told apart.
    """
    found = []
    _collect_functions(tree, "", found)
    found.sort(key=lambda item: (item[1].lineno, item[0]))
    return found


def parameter_names(function_node):
    """Every name bound by a function's signature, including *args and **kwargs."""
    args = function_node.args
    collected = [arg.arg for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)]
    if args.vararg is not None:
        collected.append(args.vararg.arg)
    if args.kwarg is not None:
        collected.append(args.kwarg.arg)
    return set(collected)


def _collect_functions(node, prefix, found):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNCTION_NODES):
            qualified = prefix + child.name
            found.append((qualified, child))
            _collect_functions(child, qualified + ".", found)
        elif isinstance(child, ast.ClassDef):
            _collect_functions(child, prefix + child.name + ".", found)
        else:
            _collect_functions(child, prefix, found)
