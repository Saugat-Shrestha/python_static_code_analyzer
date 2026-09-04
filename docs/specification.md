# PyScan — Software Specification

**Application:** Python Static Code Analyzer
**Unit:** PRT582 Software Engineering: Process and Tools
**Status:** Written before any implementation code (Task 1)

---

## 1. Overview

PyScan is a static analysis tool for Python source code. "Static" means it reads
the code as text and inspects its structure without ever running it, so analysing
a file is always safe even if that file contains an infinite loop or deletes
things when executed.

The tool parses source code into an Abstract Syntax Tree (AST) using Python's
built-in `ast` module, walks that tree with a set of independent checkers, and
returns a report containing two things: a list of **issues** (problems found in
the code) and a set of **metrics** (numbers describing the code).

Five kinds of analysis are required:

1. Cyclomatic complexity per function
2. Unused variables
3. Duplicate code
4. Naming convention violations
5. Code metrics

I chose the AST approach rather than regular expressions because regex cannot
reliably tell the difference between a real `if` statement and the word "if"
inside a string or a comment. The AST already has that resolved for us.

---

## 2. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | The system shall accept Python source code as a string and return an analysis report. |
| FR-02 | The system shall accept a path to a `.py` file and return an analysis report for that file. |
| FR-03 | The system shall calculate the cyclomatic complexity of every function and method in the source. |
| FR-04 | The system shall report an issue when a function's cyclomatic complexity exceeds a configurable threshold (default 10). |
| FR-05 | The system shall report local variables that are assigned inside a function but never read afterwards. |
| FR-06 | The system shall report imports that are never used anywhere in the module. |
| FR-07 | The system shall detect blocks of structurally identical consecutive statements that appear more than once, where the block is at least a configurable minimum length (default 4 statements). |
| FR-08 | The system shall report function and variable names that do not follow `snake_case`. |
| FR-09 | The system shall report class names that do not follow `PascalCase`. |
| FR-10 | The system shall report names that shadow a Python built-in (for example `list`, `id`, `type`). |
| FR-11 | The system shall calculate module-level metrics: total lines, code lines, comment lines, blank lines, function count, class count, average complexity, maximum complexity and comment ratio. |
| FR-12 | Every issue shall include a rule ID, a human-readable message, a line number and a severity. |
| FR-13 | Issues shall be returned sorted by line number, and then by rule ID for issues on the same line. |
| FR-14 | The thresholds and the set of enabled rules shall be configurable by the caller. |
| FR-15 | The system shall provide a command-line interface that analyses one or more files and prints the issues and metrics. |
| FR-16 | The command-line interface shall exit with status code 1 if any issue was found and 0 if the code is clean, so it can be used in a build pipeline. |
| FR-17 | The system shall raise a specific, catchable error when the source code cannot be parsed, and that error shall report the line number of the syntax problem. |

### 2.1 Rule catalogue

| Rule ID | Severity | Meaning |
|---------|----------|---------|
| `CPX001` | warning | Function cyclomatic complexity exceeds the threshold |
| `UNU001` | warning | Local variable assigned but never read |
| `UNU002` | warning | Import never used in the module |
| `DUP001` | warning | Block of statements duplicated elsewhere in the file |
| `NAM001` | warning | Function or method name is not `snake_case` |
| `NAM002` | warning | Variable name is not `snake_case` |
| `NAM003` | warning | Class name is not `PascalCase` |
| `NAM004` | warning | Function argument name is not `snake_case` |
| `NAM005` | warning | Name shadows a Python built-in |

### 2.2 How cyclomatic complexity is counted

Complexity starts at 1 and adds 1 for each of the following inside the function
body: `if`, `for`, `while`, each `except` handler, each `if` in a comprehension,
each comprehension `for` clause, each conditional expression (`x if c else y`),
each `assert`, and each extra operand in a boolean operator (so `a and b` adds 1,
`a and b and c` adds 2).

`else` does **not** add anything, because it is the fall-through path rather than
a new decision. A nested function's complexity is counted separately and is not
added to the enclosing function, so one long function does not get blamed for a
complicated helper defined inside it.

---

## 3. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | **Safety.** The tool must never import, execute or evaluate the code it is analysing. |
| NFR-02 | **Determinism.** Analysing the same input twice must produce exactly the same report, including ordering. This matters because the tool is meant to be usable in a build pipeline where a random ordering would create noisy diffs. |
| NFR-03 | **Testability.** Each checker must be usable on its own without going through the CLI, so it can be unit tested in isolation. |
| NFR-04 | **Portability.** Standard library only for the application itself. `coverage` is used for testing but is not needed to run the tool. |
| NFR-05 | **Performance.** A single source file of around 1000 lines should be analysed in well under a second, and memory use must not grow faster than the file does. |
| NFR-06 | **Robustness.** Bad input (wrong type, missing file, broken syntax) must produce a clear error rather than an unhandled crash or a partly filled report. |
| NFR-07 | **Maintainability.** Adding a new rule should mean adding one new checker module and registering it, not editing the existing checkers. |
| NFR-08 | **Usability of output.** Messages must name the specific thing that is wrong (for example which variable is unused), not just the rule that fired. |

---

## 4. Assumptions

- A-01 The input is Python 3 source code. Python 2 syntax is treated as a syntax error, which is what `ast.parse` does anyway.
- A-02 Source files are UTF-8 encoded.
- A-03 The user is interested in one file at a time. Cross-file analysis (for example, a function that is unused across the whole project) is out of scope.
- A-04 "Unused variable" is judged within a single function scope. A module-level variable is not reported, because it may be imported by another module and we cannot see that from one file.
- A-05 A name beginning with an underscore (`_`, `_unused`) is deliberately unused by convention, so it is not reported.
- A-06 Duplicate code means *structurally* duplicated, so two blocks that differ only in the names of their variables still count as duplicates. This is the useful definition; an exact-text comparison would miss nearly all real copy-paste.
- A-07 The default complexity threshold of 10 follows the common convention used by tools like `flake8`'s McCabe plugin. It is configurable because different projects draw the line in different places.

---

## 5. Constraints

- C-01 Python 3.9 is the target runtime (this is the version installed on my machine), so no `match` statements or newer syntax in the analyser's own code.
- C-02 Only the standard library may be used in the application package.
- C-03 Tests must use `unittest`, matching the framework taught in Tutorial 3.
- C-04 Because the analysis is static, anything decided at runtime cannot be detected. For example a variable read via `globals()["x"]` or `eval` will look unused. This is a known and accepted limitation, not a bug.
- C-05 The tool reports issues; it does not fix them.

---

## 6. Expected System Behaviours

These are the concrete behaviours the test suite is built around.

| # | Given | When | Then |
|---|-------|------|------|
| B-01 | A function with no branches at all | complexity is calculated | its cyclomatic complexity is 1 |
| B-02 | A function containing one `if` | complexity is calculated | its complexity is 2 |
| B-03 | A function whose complexity is 11 with a threshold of 10 | the source is analysed | one `CPX001` issue is reported naming that function |
| B-04 | A function that assigns `total = 0` and never reads `total` | the source is analysed | one `UNU001` issue is reported naming `total` |
| B-05 | A function that assigns a variable and later reads it | the source is analysed | no unused-variable issue is reported |
| B-06 | A module importing `os` and never using it | the source is analysed | one `UNU002` issue is reported naming `os` |
| B-07 | Two functions containing the same five statements with different variable names | the source is analysed | one `DUP001` issue group is reported linking both locations |
| B-08 | A function named `calculateTotal` | the source is analysed | one `NAM001` issue is reported |
| B-09 | A class named `my_class` | the source is analysed | one `NAM003` issue is reported |
| B-10 | A variable named `list` | the source is analysed | one `NAM005` builtin-shadowing issue is reported |
| B-11 | A 10-line file with 2 blank lines and 3 comment lines | metrics are calculated | `total_lines` is 10, `blank_lines` is 2, `comment_lines` is 3 and `code_lines` is 5 |
| B-12 | Any source producing several issues on different lines | the report is returned | issues are ordered by ascending line number |
| B-13 | A file that is completely clean | the CLI is run on it | it prints a success message and exits with code 0 |
| B-14 | A file containing at least one issue | the CLI is run on it | it exits with code 1 |
| B-15 | A configuration disabling the naming rules | the source is analysed | no `NAM*` issues appear even though violations exist |

---

## 7. Boundary Conditions

Boundaries are where off-by-one mistakes live, so each of these gets a test on
both sides of the line.

| ID | Boundary | Expected |
|----|----------|----------|
| BC-01 | Complexity exactly equal to the threshold (10) | **Not** reported — the rule is "exceeds", not "reaches" |
| BC-02 | Complexity one above the threshold (11) | Reported |
| BC-03 | Duplicate block one statement shorter than the minimum | Not reported |
| BC-04 | Duplicate block exactly the minimum length | Reported |
| BC-05 | Empty source string | Valid input; report has zero issues and all metrics zero |
| BC-06 | Source containing only comments and blank lines | Valid; `code_lines` is 0, `function_count` is 0 |
| BC-07 | A file with no trailing newline | Line counting must still be correct |
| BC-08 | A variable named exactly `_` | Not reported as unused |
| BC-09 | A single-character variable name such as `i` | Valid `snake_case`, not reported |
| BC-10 | A one-statement function repeated many times | Not reported as duplication (below minimum block size) |
| BC-11 | Complexity threshold set to 0 | Every function is reported |
| BC-12 | Average complexity of a file with zero functions | 0.0, not a division-by-zero crash |

BC-12 in particular is the sort of thing that gets missed: the natural way to
write an average is `total / count`, which blows up on an empty file.

---

## 8. Invalid Input Scenarios

| ID | Input | Expected behaviour |
|----|-------|--------------------|
| IN-01 | Source with a syntax error (`def f(:`) | Raise `SourceParseError` including the line number |
| IN-02 | Source that is not a string (e.g. `42`, `None`, a list) | Raise `InvalidSourceError` |
| IN-03 | A file path that does not exist | Raise `SourceFileError` |
| IN-04 | A path pointing at a directory | Raise `SourceFileError` |
| IN-05 | A negative complexity threshold | Raise `ConfigurationError` |
| IN-06 | A minimum duplicate block size below 1 | Raise `ConfigurationError` |
| IN-07 | An unknown rule ID in the enabled-rules configuration | Raise `ConfigurationError` naming the unknown rule |
| IN-08 | Source containing a null byte | Raise `SourceParseError` (the parser rejects it) |
| IN-09 | CLI run with no file arguments | Print usage and exit non-zero |

All of these errors inherit from one base class, `AnalyzerError`, so a caller who
does not care about the distinction can catch just the one type. That decision
comes from the password validator in Tutorial 3, where a single custom exception
made the tests much easier to write than returning `True`/`False` and losing the
reason for the failure.

---

## 9. Notes added during development

**NFR-05.** The original wording claimed the tool "walks the tree a small fixed
number of times, so cost grows roughly linearly". That was wrong. Duplicate
detection compares every block of every length against every other, which is
inherently more than a fixed number of passes, and the first implementation used
1.26 GB on a 1000-line file. After the rewrite described in the development log,
time is linear in file size and memory is close to flat, so the requirement now
holds — but the original justification for believing it did not.

The remaining cost is dominated by duplicate detection, which is roughly linear
for ordinary code because near-unique blocks are discarded after the first round.
A pathological file made of hundreds of identical statements would still be
quadratic. That is an accepted limit rather than something the tool guards
against.

---

## 10. Out of Scope

- Type checking or any form of type inference
- Cross-file / whole-project analysis
- Automatically fixing the issues found
- Analysing anything other than Python
- A graphical interface
