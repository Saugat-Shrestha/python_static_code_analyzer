"""The public entry point: parse the source, run every checker, build a report."""

import ast
import os
from dataclasses import dataclass
from typing import List

from pyscan import complexity, duplication, naming, unused
from pyscan.config import AnalyzerConfig
from pyscan.errors import InvalidSourceError, SourceFileError, SourceParseError
from pyscan.metrics import calculate_metrics
from pyscan.models import AnalysisReport


@dataclass(frozen=True)
class AnalysisContext:
    """Everything a checker needs, worked out once and shared.

    The tree is parsed a single time and handed to every checker, rather than
    each checker parsing the source again.
    """

    source: str
    lines: List[str]
    tree: ast.Module
    config: AnalyzerConfig


CHECKERS = (complexity.check, duplication.check, naming.check, unused.check)


def parse_source(source):
    """Parse source text into an AST, converting parser failures into our own errors."""
    if not isinstance(source, str):
        raise InvalidSourceError(
            "source must be a string, got %s" % type(source).__name__
        )
    try:
        return ast.parse(source)
    except SyntaxError as error:
        raise SourceParseError(
            "could not parse source: %s (line %s)" % (error.msg, error.lineno),
            line=error.lineno,
        ) from error
    except ValueError as error:
        # ast.parse raises ValueError rather than SyntaxError for null bytes.
        raise SourceParseError("could not parse source: %s" % error) from error


def analyze_source(source, config=None):
    """Analyse Python source code and return a report."""
    config = config if config is not None else AnalyzerConfig()
    tree = parse_source(source)
    context = AnalysisContext(
        source=source,
        lines=source.splitlines(),
        tree=tree,
        config=config,
    )

    issues = []
    for checker in CHECKERS:
        issues.extend(checker(context))

    issues = [issue for issue in issues if config.is_enabled(issue.rule_id)]
    issues.sort(key=lambda issue: issue.sort_key)
    return AnalysisReport(
        issues=tuple(issues),
        metrics=calculate_metrics(tree, source),
    )


def analyze_file(path, config=None):
    """Read a Python file from disk and analyse it."""
    return analyze_source(read_source(path), config)


def read_source(path):
    """Read a source file, turning any filesystem problem into SourceFileError."""
    if os.path.isdir(path):
        raise SourceFileError("'%s' is a directory, not a file" % path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError as error:
        raise SourceFileError("no such file: '%s'" % path) from error
    except OSError as error:
        raise SourceFileError("could not read '%s': %s" % (path, error)) from error
    except UnicodeDecodeError as error:
        raise SourceFileError("'%s' is not valid UTF-8 text" % path) from error
