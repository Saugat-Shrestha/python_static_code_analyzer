"""Code metrics: line counts and complexity summaries.

Lines are classified by looking at the text, which is simple and predictable.
A line whose first non-space character is `#` is a comment; anything else with
content on it is code, including a line that happens to end in a comment. A
docstring counts as code, on the basis that it is part of the module rather
than a note about it.
"""

import ast

from pyscan.astutils import iter_functions
from pyscan.complexity import function_complexities
from pyscan.models import Metrics


def calculate_metrics(tree, source):
    blank, comment, code = _classify_lines(source)
    scores = [result.complexity for result in function_complexities(tree)]
    documented = comment + code

    return Metrics(
        total_lines=blank + comment + code,
        code_lines=code,
        comment_lines=comment,
        blank_lines=blank,
        function_count=len(iter_functions(tree)),
        class_count=sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)),
        average_complexity=round(sum(scores) / len(scores), 2) if scores else 0.0,
        max_complexity=max(scores) if scores else 0,
        comment_ratio=round(comment / documented, 3) if documented else 0.0,
    )


def _classify_lines(source):
    blank = comment = code = 0
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif stripped.startswith("#"):
            comment += 1
        else:
            code += 1
    return blank, comment, code
