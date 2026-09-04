# PyScan — Test Design

Written before implementation, alongside `specification.md` (Task 1).

## How the suite is organised

One test module per checker, plus one for the public API and one for the CLI.
Each test module can be run on its own, which is what makes the red-green-refactor
loop quick — I do not want to run the whole suite to find out whether one
function returns 2 instead of 1.

| Test module | Covers |
|---|---|
| `test_complexity.py` | Cyclomatic complexity counting and the threshold rule |
| `test_unused.py` | Unused local variables and unused imports |
| `test_duplication.py` | Structural duplicate-block detection |
| `test_naming.py` | snake_case / PascalCase / builtin shadowing |
| `test_metrics.py` | Line counting and aggregate numbers |
| `test_analyzer.py` | The public `analyze_source` / `analyze_file` API, ordering, configuration, error handling |
| `test_cli.py` | Argument handling, output text, exit codes |

Tests use small inline source snippets written as triple-quoted strings rather
than fixture files. This keeps the input visible right next to the assertion,
so when a test fails you can see the exact code that broke it without opening
another file.

---

## Test groups and why each one exists

### Group 1 — Complexity counting (normal behaviour)

**What is tested:** that a function with no branches scores 1, and that each
decision point (`if`, `elif`, `for`, `while`, `except`, `and`, `or`, ternary,
comprehension `if`, `assert`) adds exactly 1.

**Why it is necessary:** cyclomatic complexity is the one part of this tool that
produces a *number* rather than a yes/no. If the number is wrong by one, every
threshold test downstream is also wrong, but nothing crashes, so the bug would
be invisible without direct tests.

**Defect prevented:** miscounting decision points. The two classic mistakes are
counting an `if/else` as 2 (the `else` is not a decision, it is the fall-through)
and counting `a and b and c` as 1 instead of 2. I test both of these on purpose
because I expected AI-generated code to get them wrong, and the second one turned
out to be exactly right.

---

### Group 2 — Complexity threshold (boundary)

**What is tested:** a function at complexity 10 with threshold 10 is clean; the
same function at 11 is reported. Also threshold 0 reports everything.

**Why it is necessary:** FR-04 says "exceeds", which is `>`, not `>=`. Nothing
in the code itself makes that obvious.

**Defect prevented:** off-by-one at the threshold. This would produce a
false positive on every function sitting exactly on the limit — the most
annoying possible failure mode for a linter, because users stop trusting it.

---

### Group 3 — Unused variables (normal + negative)

**What is tested:** a variable assigned and never read is reported; a variable
assigned and later read is not; a variable read before being reassigned is not;
a parameter is never reported as an unused variable; `_` is never reported;
augmented assignment (`x += 1`) counts as both a read and a write.

**Why it is necessary:** this checker is the easiest one to make
over-enthusiastic. A checker that reports variables which *are* used is worse
than no checker at all.

**Defect prevented:** false positives from only looking at `ast.Store` contexts
and forgetting that the same name appears in `ast.Load` context elsewhere. Also
prevents reporting function parameters, which are not "unused variables" in the
sense we mean and would fire constantly on interface methods.

---

### Group 4 — Unused imports

**What is tested:** an unused `import os` is reported; a used one is not;
`from x import y as z` is tracked under the alias `z`, not `y`.

**Why it is necessary:** the aliasing case is genuinely easy to get wrong and it
is common in real code (`import numpy as np`).

**Defect prevented:** reporting `np` as unused because the checker recorded the
name `numpy`, or vice versa.

---

### Group 5 — Duplicate code (normal + boundary)

**What is tested:** two identical five-statement blocks are reported once as a
group with both line numbers; blocks that differ only in variable names are
still reported; a block of exactly the minimum size is reported; one statement
shorter is not; three copies produce one group with three locations, not three
separate issues.

**Why it is necessary:** this is the most algorithmically involved checker. It
uses overlapping sliding windows, which means a genuinely duplicated ten-statement
block will match at window start 0, 1, 2, 3 and so on. Without care, one
copy-paste produces seven near-identical warnings.

**Defect prevented:** duplicate reporting of duplicates. Also prevents the
opposite bug, where de-duplicating too aggressively hides a second real
occurrence.

---

### Group 6 — Naming conventions

**What is tested:** `calculateTotal` and `CalculateTotal` are flagged as
functions; `calculate_total` is not; `my_class` is flagged as a class but
`MyClass` is not; `list` and `id` are flagged as builtin shadowing; a
single-character name like `i` is accepted; a dunder method like `__init__` is
accepted.

**Why it is necessary:** the dunder case is the one that will break a naive
implementation. `__init__` is not snake_case by a strict reading, but flagging
it would fire on essentially every class ever written.

**Defect prevented:** a regex that is either too strict (rejects `__init__`,
rejects `_private`) or too loose (accepts `calculateTotal` because it only
checks for the absence of spaces).

---

### Group 7 — Metrics

**What is tested:** line counts on a snippet with a known mix of code, comments
and blank lines; a comment on the same line as code counts as a code line;
average and maximum complexity; an empty file; a file with no functions.

**Why it is necessary:** metrics are pure arithmetic over the source, so they
are cheap to test exhaustively, and the empty-file case is a real crash risk
(BC-12, dividing by zero functions).

**Defect prevented:** `ZeroDivisionError` on an empty or function-free file, and
double-counting a trailing-comment line as both a code line and a comment line.

---

### Group 8 — Public API, ordering and configuration

**What is tested:** `analyze_source` returns issues sorted by line then rule ID;
`analyze_file` reads a real temporary file; disabling a rule removes exactly
those issues and leaves the others; the same input analysed twice gives an
identical report.

**Why it is necessary:** NFR-02 requires deterministic output. Dictionaries and
sets are used inside the duplicate checker, and any leak of set-iteration order
into the output would make the tool unusable in CI.

**Defect prevented:** non-deterministic ordering, and a configuration flag that
silently does nothing.

---

### Group 9 — Invalid input and exceptional cases

**What is tested:** every row of the invalid-input table in the specification —
syntax errors, wrong argument type, missing file, directory instead of file,
negative threshold, unknown rule name.

**Why it is necessary:** the specification promises specific exception types
(NFR-06). A promise about error behaviour that is not tested is not a promise.

**Defect prevented:** a raw `SyntaxError` or `TypeError` escaping to the caller
instead of the documented `AnalyzerError` subclass, which would break any code
written against the documented interface.

---

### Group 10 — CLI

**What is tested:** exit code 0 on clean input, 1 on input with issues, non-zero
with a usage message when no arguments are given, and that the printed output
actually contains the rule ID and line number.

**Why it is necessary:** FR-16 makes exit codes part of the contract, since the
tool is meant to be usable in a pipeline. Exit codes are invisible in normal
manual use, so they only get checked if a test checks them.

**Defect prevented:** a CLI that finds problems, prints them, and then exits 0 —
meaning a build would pass while the tool was actively reporting failures.

---

### Group 11 — Regression tests

Added during development rather than up front, because you cannot design a
regression test for a bug you have not hit yet. Each one is tagged with a
comment saying which defect it locks down. They are listed in section 3 below.

---

## 2. Traceability matrix

Every requirement, behaviour, boundary and invalid input in the specification
maps to at least one named test. Tests are tagged in the source with the ID they
cover, so the mapping can be checked in both directions — searching the `tests/`
directory for `BC-04` finds the test, and reading the test tells you which
requirement it exists for.

### 2.1 Functional requirements

| ID | Requirement | Test module | Representative test |
|----|-------------|-------------|---------------------|
| FR-01 | Analyse a source string | `test_analyzer` | `test_analyze_source_returns_a_report` |
| FR-02 | Analyse a file path | `test_analyzer` | `test_reads_and_analyses_a_real_file` |
| FR-03 | Complexity of every function | `test_complexity` | `test_straight_line_function_scores_one`, `test_single_if_adds_one` |
| FR-04 | Report complexity over threshold | `test_complexity` | `test_complexity_one_above_threshold_is_reported` |
| FR-05 | Report unused locals | `test_unused` | `test_variable_assigned_and_never_read_is_reported` |
| FR-06 | Report unused imports | `test_unused` | `test_unused_plain_import_is_reported` |
| FR-07 | Detect duplicated blocks | `test_duplication` | `test_blocks_differing_only_in_variable_names_are_still_duplicates` |
| FR-08 | Function/variable snake_case | `test_naming` | `test_camel_case_function_is_reported` |
| FR-09 | Class PascalCase | `test_naming` | `test_snake_case_class_is_reported` |
| FR-10 | Built-in shadowing | `test_naming` | `test_variable_shadowing_a_builtin_is_reported` |
| FR-11 | Module metrics | `test_metrics` | `test_lines_are_split_into_code_comment_and_blank` |
| FR-12 | Issue fields present | `test_analyzer` | `test_every_issue_carries_the_documented_fields` |
| FR-13 | Sorted by line then rule | `test_analyzer` | `test_issues_are_sorted_by_line_number`, `test_issues_on_the_same_line_are_sorted_by_rule_id` |
| FR-14 | Configurable thresholds and rules | `test_analyzer` | `test_disabling_a_rule_removes_only_that_rule` |
| FR-15 | Command-line interface | `test_cli` | `test_all_files_are_analysed` |
| FR-16 | Exit codes | `test_cli` | `test_clean_file_exits_zero`, `test_file_with_issues_exits_one` |
| FR-17 | Catchable parse error with a line | `test_analyzer` | `test_syntax_error_raises_source_parse_error_with_a_line` |

### 2.2 Non-functional requirements

| ID | Requirement | Test module | Test |
|----|-------------|-------------|------|
| NFR-01 | Never executes the analysed code | `test_analyzer` | `test_analysing_code_never_executes_it`, `test_code_that_would_crash_if_run_analyses_normally` |
| NFR-02 | Deterministic output | `test_analyzer` | `test_the_same_input_always_gives_the_same_report` |
| NFR-03 | Checkers usable in isolation | `test_complexity` | `test_straight_line_function_scores_one` calls `function_complexities` directly, with no CLI and no file I/O |
| NFR-04 | Standard library only | — | Structural: nothing in `pyscan/` imports a third-party package |
| NFR-05 | 1000 lines in well under a second | `test_analyzer` | `test_a_thousand_line_file_is_analysed_in_well_under_a_second` |
| NFR-06 | Clear errors on bad input | `test_analyzer` | The whole of `TestInvalidSource` and `TestAnalyzeFile` |
| NFR-07 | A new rule means a new module | — | Structural: `CHECKERS` in `analyzer.py` is a tuple of `check(context)` functions |
| NFR-08 | Messages name the specific thing | `test_analyzer` | `test_messages_name_the_specific_thing_that_is_wrong` |

NFR-04 and NFR-07 are properties of the code's shape rather than its behaviour,
so there is no meaningful runtime assertion for them. I have marked them as
structural rather than pretending a test covers them.

### 2.3 Expected behaviours

| ID | Test module | Test |
|----|-------------|------|
| B-01 | `test_complexity` | `test_straight_line_function_scores_one` |
| B-02 | `test_complexity` | `test_single_if_adds_one` |
| B-03 | `test_complexity` | `test_complexity_one_above_threshold_is_reported` |
| B-04 | `test_unused` | `test_variable_assigned_and_never_read_is_reported` |
| B-05 | `test_unused` | `test_variable_that_is_read_later_is_not_reported` |
| B-06 | `test_unused` | `test_unused_plain_import_is_reported` |
| B-07 | `test_duplication` | `test_blocks_differing_only_in_variable_names_are_still_duplicates` |
| B-08 | `test_naming` | `test_camel_case_function_is_reported` |
| B-09 | `test_naming` | `test_snake_case_class_is_reported` |
| B-10 | `test_naming` | `test_variable_shadowing_a_builtin_is_reported` |
| B-11 | `test_metrics` | `test_lines_are_split_into_code_comment_and_blank` |
| B-12 | `test_analyzer` | `test_issues_are_sorted_by_line_number` |
| B-13 | `test_cli` | `test_clean_file_exits_zero` |
| B-14 | `test_cli` | `test_file_with_issues_exits_one` |
| B-15 | `test_analyzer` | `test_disabling_a_rule_removes_only_that_rule` |

### 2.4 Boundary conditions

| ID | Boundary | Test |
|----|----------|------|
| BC-01 | Complexity == threshold | `test_complexity_equal_to_threshold_is_not_reported` |
| BC-02 | Complexity == threshold + 1 | `test_complexity_one_above_threshold_is_reported` |
| BC-03 | Duplicate one below minimum | `test_block_one_statement_below_the_minimum_is_not_reported` |
| BC-04 | Duplicate exactly at minimum | `test_block_exactly_at_the_minimum_is_reported` |
| BC-05 | Empty source | `test_empty_source_has_zero_lines`, `test_empty_source_is_valid_not_an_error` |
| BC-06 | Comments only | `test_file_of_only_comments_has_no_code_lines` |
| BC-07 | No trailing newline | `test_missing_trailing_newline_still_counts_correctly` |
| BC-08 | Variable named `_` | `test_underscore_is_never_reported` |
| BC-09 | Single-character name | `test_single_letter_variable_is_clean` |
| BC-10 | One statement repeated | `test_repeated_single_statement_is_not_reported_at_default_minimum` |
| BC-11 | Threshold of 0 | `test_threshold_of_zero_reports_every_function` |
| BC-12 | Average over zero functions | `test_empty_file_does_not_divide_by_zero`, `test_file_with_no_functions_does_not_divide_by_zero` |

### 2.5 Invalid inputs and exceptions

| ID | Input | Test |
|----|-------|------|
| IN-01 | Syntax error | `test_syntax_error_raises_source_parse_error_with_a_line` |
| IN-02 | Non-string source | `test_non_string_source_raises_invalid_source_error` |
| IN-03 | Missing file | `test_missing_file_raises_source_file_error` |
| IN-04 | Directory as path | `test_directory_path_raises_source_file_error` |
| IN-05 | Negative threshold | `test_negative_complexity_threshold_is_rejected` |
| IN-06 | Duplicate minimum below 1 | `test_duplicate_minimum_below_one_is_rejected` |
| IN-07 | Unknown rule ID | `test_unknown_rule_id_is_rejected_and_named` |
| IN-08 | Null byte | `test_null_byte_raises_source_parse_error` |
| IN-09 | CLI with no arguments | `test_no_arguments_prints_usage_and_exits_with_an_error` |

Two further exception cases are tested that the specification did not predict:
a file that is not valid UTF-8 (`test_file_that_is_not_utf8_raises_source_file_error`)
and a file the user has no permission to read
(`test_unreadable_file_raises_source_file_error`). Both were found while closing
coverage gaps.

---

## 3. Regression tests

Each of these was written in response to a specific defect that had already
happened, so that the same mistake cannot come back unnoticed.

| Test | Defect it locks down |
|------|----------------------|
| `test_nested_function_is_measured_separately` | A nested `def` in a function body had its branches counted against the parent, because the scope guard only checked child nodes |
| `test_names_listed_in_dunder_all_count_as_used` | Every re-export in `__init__.py` was reported as an unused import |
| `test_dunder_all_written_as_a_tuple_also_counts` | Same defect, with `__all__` written as a tuple |
| `test_dunder_all_built_dynamically_is_ignored_without_crashing` | The fix for the above must not crash or guess when `__all__` is computed |
| `test_non_string_entries_in_dunder_all_are_skipped` | Same fix, given a non-string element |
| `test_the_same_source_does_report_when_the_pair_stops_overlapping` | Paired with the overlap test so that a checker cannot satisfy one by breaking the other |
| `test_dunder_method_is_clean` | A snake_case pattern that rejected `__init__` and `_helper` |
| `test_upper_case_constant_is_clean` | No constant handling at all, so every `MAX_SIZE` was reported |
| `test_empty_file_does_not_divide_by_zero` | `sum(scores) / len(scores)` with no guard |
| `test_a_thousand_line_file_is_analysed_in_well_under_a_second` | Duplicate detection stored the text of every block of every length, using 1.26 GB on a 1000-line file |
| `test_no_module_exceeds_the_default_complexity_limit` | `cli.main` drifting over the limit the tool itself enforces |
| `test_every_module_is_free_of_issues` | Any regression that the tool is capable of detecting in its own source |

The last two are the self-analysis tests. They are the broadest safety net in the
suite, because they do not test one specific defect — they test that the analyser
still holds its own code to the standard it enforces on everyone else. Both of
them have already caught a real regression: the rewritten duplicate checker was
committed at complexity 12, and the self-analysis test failed immediately.
