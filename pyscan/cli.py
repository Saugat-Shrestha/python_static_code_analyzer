"""Command-line interface for PyScan.

`main` takes its arguments and its output streams as parameters rather than
reaching for `sys.argv` and `sys.stdout`. That one decision is what makes the
CLI testable: a test can call `main([...], stdout=StringIO())` and read the
output back, with no subprocess and no monkey-patching.

Exit codes are part of the contract so the tool can be used in a build:
    0  nothing to report
    1  the code was analysed successfully and problems were found
    2  the tool could not do its job (bad file, bad options, unparsable source)
"""

import argparse
import sys

from pyscan.analyzer import analyze_file
from pyscan.config import RULE_DESCRIPTIONS, AnalyzerConfig
from pyscan.errors import AnalyzerError

EXIT_CLEAN = 0
EXIT_ISSUES = 1
EXIT_ERROR = 2

USAGE = "usage: pyscan [options] FILE [FILE ...]"


def main(argv=None, stdout=None, stderr=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = _or_default(stdout, sys.stdout)
    stderr = _or_default(stderr, sys.stderr)

    parser = _build_parser()
    try:
        options = parser.parse_args(argv)
    except SystemExit as exit_request:
        # argparse exits by itself on --help or a malformed option.
        return _exit_code_of(exit_request)

    if options.list_rules:
        _print_rules(stdout)
        return EXIT_CLEAN

    if not options.files:
        _print_usage_error(stderr)
        return EXIT_ERROR

    try:
        config = _build_config(options)
        total_issues = _analyse_files(options.files, config, stdout, options.quiet)
    except AnalyzerError as error:
        print("error: %s" % error, file=stderr)
        return EXIT_ERROR

    _print_summary(total_issues, len(options.files), stdout)
    return EXIT_ISSUES if total_issues else EXIT_CLEAN


def _or_default(value, fallback):
    return fallback if value is None else value


def _exit_code_of(exit_request):
    return exit_request.code or EXIT_CLEAN


def _print_usage_error(stream):
    print(USAGE, file=stream)
    print("error: at least one file is required", file=stream)


def _build_config(options):
    return AnalyzerConfig(
        max_complexity=options.max_complexity,
        min_duplicate_statements=options.min_duplicate_statements,
        disabled_rules=frozenset(options.disable),
    )


def _analyse_files(paths, config, stdout, quiet):
    """Analyse every path, printing as we go, and return the total issue count."""
    total_issues = 0
    for path in paths:
        report = _analyse_one(path, config)
        total_issues += len(report.issues)
        _print_report(path, report, stdout, quiet=quiet)
    return total_issues


def _analyse_one(path, config):
    """Analyse one file, adding the path to any error so the user knows which."""
    try:
        return analyze_file(path, config)
    except AnalyzerError as error:
        raise AnalyzerError("%s: %s" % (path, error)) from error


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="pyscan",
        description="Static analysis for Python source files.",
    )
    parser.add_argument("files", nargs="*", help="Python files to analyse")
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=AnalyzerConfig.max_complexity,
        help="highest cyclomatic complexity a function may have (default: %(default)s)",
    )
    parser.add_argument(
        "--min-duplicate-statements",
        type=int,
        default=AnalyzerConfig.min_duplicate_statements,
        help="smallest block counted as duplication (default: %(default)s)",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="RULE",
        help="turn off a rule; may be given more than once",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print issues only, without the metrics summary",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="print every rule id with a short description and exit",
    )
    return parser


def _print_rules(stream):
    for rule_id in sorted(RULE_DESCRIPTIONS):
        print("%s  %s" % (rule_id, RULE_DESCRIPTIONS[rule_id]), file=stream)


def _print_report(path, report, stream, quiet):
    print(path, file=stream)

    if report.issues:
        for issue in report.issues:
            print("  %d:%s  %s" % (issue.line, issue.rule_id, issue.message), file=stream)
    else:
        print("  no issues found", file=stream)

    if not quiet:
        print("  %s" % _format_metrics(report.metrics), file=stream)
    print("", file=stream)


def _format_metrics(metrics):
    return (
        "%d lines (%d code, %d comment, %d blank), "
        "%d functions, %d classes, "
        "average complexity %.2f, highest complexity %d"
        % (
            metrics.total_lines,
            metrics.code_lines,
            metrics.comment_lines,
            metrics.blank_lines,
            metrics.function_count,
            metrics.class_count,
            metrics.average_complexity,
            metrics.max_complexity,
        )
    )


def _print_summary(total_issues, file_count, stream):
    if total_issues == 0:
        print("no issues found in %d file(s)" % file_count, file=stream)
    else:
        print("%d issue(s) found in %d file(s)" % (total_issues, file_count), file=stream)
