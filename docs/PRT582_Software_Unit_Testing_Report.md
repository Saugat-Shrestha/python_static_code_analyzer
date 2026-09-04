```{=typst}
#align(center)[
  #image("cdu-logo.png", width: 4.5cm)
  #v(1.6cm)
  #set par(justify: false, leading: 0.55em, spacing: 0.55em)
  #set text(size: 12pt)
  Software Engineering: Process and Tools
  #v(0.35cm)
  Unit Code: PRT582
  #v(0.55cm)
  #text(size: 14pt, weight: "bold")[Software Unit Testing Report]
  #v(0.75cm)
  Name: Saugat Shrestha \
  Student ID: S403036 \
  Campus: Sydney \
  Submission Date: 2 September 2026 \
  Submitted To: Abdullah Al-Amoodi
  #v(0.45cm)
  #text(size: 11pt)[
    Application built: Python Static Code Analyzer ("PyScan") \
    GitHub repository: https://github.com/Saugat-Shrestha/python_static_code_analyzer
  ]
]
#pagebreak()
```

```{=typst}
#heading(level: 2, outlined: false)[Table of Contents]
#outline(title: none, depth: 3, indent: auto)
#pagebreak()
```

## 1. Introduction

For this assignment I built a static code analyser for Python called PyScan. It
reads Python source files and reports on them without running them, which is what
"static" means. It checks five things: the cyclomatic complexity of each function,
variables and imports that are never used, blocks of duplicated code, names that
break the usual Python conventions, and a set of code metrics such as line counts
and average complexity.

I picked this option out of the four because it suited unit testing better than
the others. Almost everything the analyser does is a pure function — source code
goes in, a report comes out — so there is no database, no interface and no
randomness to work around in the tests. That meant I could spend my time on the
actual point of the assignment, which is the testing, rather than on setting up
test fixtures. It also has a lot of natural edge cases: an empty file, a file
with no functions, a name like `__init__` that looks like a violation but is not.
Those made good boundary tests.

The whole thing was built using AI-assisted test-driven development in Cursor. For
every feature, the loop was the same: I wrote the tests first and ran them so I
could see them fail, then asked the AI for an implementation, then ran the tests
again and fixed whatever came back red. I did not ask the AI to write the whole
application in one go, and I did not accept anything without reading it.

The final result is 190 automated tests, all passing, with 99% branch coverage of
the application code. Along the way the AI produced code that was mostly good but
occasionally wrong in ways that were easy to miss, and my own tests turned out to
be wrong twice. Both of those experiences are written up in this report because
they are the most useful things I learned.

Three documents in the repository support this report and go into more detail:
`docs/specification.md` (written before any code existed), `docs/test-design.md`,
and `docs/ai-development-log.md`, which is a running record of the session.

---

## 2. Requirements Analysis

Before writing a single line of implementation code I wrote a specification. The
full version is in `docs/specification.md`. This section summarises it and
explains the decisions that mattered.

### 2.1 Functional requirements

There are seventeen functional requirements. The core ones are that the system
accepts either a source string or a file path and returns a report; that it
calculates complexity for every function and flags the ones over a threshold;
that it finds unused locals and unused imports, duplicated statement blocks and
naming violations; and that every issue carries a rule ID, a message, a line
number and a severity.

Two of the requirements are less obvious but turned out to matter a lot:

- **FR-13:** issues must be sorted by line number, then by rule ID. Without this
  the output ordering depends on the order the checkers happen to run in, which is
  an implementation detail that should not leak out.
- **FR-16:** the command-line tool exits with status 1 if it found anything and 0
  if the code is clean. This is what lets the tool be used in a build pipeline.
  It is also completely invisible when you run the tool by hand, which is exactly
  why it needed to be written down as a requirement and then tested.

### 2.2 Non-functional requirements

Eight non-functional requirements. The two that shaped the design most were:

- **Determinism (NFR-02).** The same input must always produce the same report,
  including the ordering. The duplicate-code checker uses dictionaries and sets
  internally, and if set iteration order leaked into the output, the tool would
  produce different results on different runs. In a build pipeline that would show
  up as random diffs and people would stop trusting it.
- **Testability (NFR-03).** Every checker has to be usable on its own, without
  going through the command line. This is why `main()` in the CLI takes its
  arguments and its output streams as parameters instead of reaching for
  `sys.argv` and `sys.stdout` directly. That one decision meant the CLI tests
  could call `main([...], stdout=StringIO())` and read the output back, with no
  subprocesses and no monkey-patching.

### 2.3 Assumptions

Seven assumptions are recorded. The two that had the biggest effect on the code:

- **A-04:** "unused variable" is judged within a single function only. A
  module-level variable is never reported, because another module might import it
  and we cannot see that from one file.
- **A-06:** duplicate code means *structurally* duplicated, so two blocks that
  differ only in their variable names still count. This is the useful definition.
  If I had compared the text directly, the checker would have missed almost all
  real copy-paste, because the first thing people do after pasting is rename the
  variables.

I also decided early on to parse the code into an Abstract Syntax Tree using
Python's built-in `ast` module rather than using regular expressions. A regex
cannot tell the difference between a real `if` statement and the word "if" inside
a string or a comment. The AST has already solved that problem, so complexity
counting becomes a matter of walking a tree and counting node types.

### 2.4 Constraints

Python 3.9 is the target, because that is what is installed on my machine, so
nothing newer than 3.9 syntax can be used. The application uses only the standard
library — `coverage` is needed for measuring the tests but not for running the
tool. Tests use `unittest`, matching Tutorial 3.

The most important constraint is a conceptual one (C-04): static analysis cannot
see anything decided at runtime. A variable read through `globals()["x"]` or
`eval` will look unused to PyScan. That is a limitation of the whole approach
rather than a bug, so I wrote it into the specification rather than pretending
the tool is more capable than it is.

### 2.5 Expected system behaviours

The specification lists fifteen expected behaviours in given/when/then form, which
became the backbone of the test suite. A few examples:

| # | Given | When | Then |
|---|---|---|---|
| B-01 | A function with no branches | complexity is calculated | complexity is 1 |
| B-04 | `total = 0` assigned and never read | source is analysed | one `UNU001` issue naming `total` |
| B-07 | Two functions with the same five statements, different variable names | source is analysed | one `DUP001` group linking both |
| B-11 | A 10-line file, 2 blank and 3 comment lines | metrics calculated | total 10, blank 2, comment 3, code 5 |
| B-14 | A file with at least one issue | CLI is run | exits with code 1 |

### 2.6 Boundary conditions

Twelve boundary conditions, each of which gets tested on both sides of the line.
The ones worth pointing out:

- **BC-01 and BC-02:** complexity exactly at the threshold must be clean, and one
  above must be reported. FR-04 says "exceeds", which is `>` and not `>=`, but
  nothing in the code makes that obvious. Getting it wrong would produce a false
  positive on every function sitting exactly on the limit, which is the most
  annoying possible failure for a linter.
- **BC-12:** the average complexity of a file with no functions. The natural way
  to write an average is `total / count`, and that crashes on an empty file. I put
  this in the specification specifically because I expected it to be forgotten,
  and it was.
- **BC-08:** a variable named `_` must never be reported as unused, because a
  leading underscore is the conventional way of saying "I know, I do not need
  this value".

### 2.7 Invalid input scenarios

Nine invalid inputs are specified: a syntax error, a non-string source, a missing
file, a directory instead of a file, a negative threshold, a duplicate minimum
below 1, an unknown rule ID, a null byte, and running the CLI with no arguments.

Every one of these raises a specific exception that inherits from a single base
class, `AnalyzerError`. That idea came directly from the password validator in
Tutorial 3, where using a custom exception rather than returning `True`/`False`
made the tests much easier to write, because the failure carried a reason with it.

---

## 3. Test Design

The full test design is in `docs/test-design.md`. There is one test module per
checker, plus one for the public API and one for the CLI, so that a single module
can be run on its own during the red-green-refactor loop.

Tests use small inline source snippets written as triple-quoted strings rather
than separate fixture files. That keeps the input visible right next to the
assertion, so when a test fails you can see the exact code that broke it without
opening anything else.

Eleven test groups were designed up front. For each group the design records what
behaviour is tested, why the test is needed and what defect it prevents. Rather
than repeat all eleven here, these are the ones where the reasoning mattered most.

### 3.1 Traceability

Every ID in the specification maps to at least one named test, and the mapping
works in both directions. Tests carry the ID they cover as a comment, so
searching the `tests/` directory for `BC-04` finds the test that proves it, and
reading any test tells you which requirement it exists for:

```python
def test_complexity_equal_to_threshold_is_not_reported(self):
    # BC-01. The rule is "exceeds", so exactly 10 must stay clean.
```

The full matrix is in `docs/test-design.md` section 2. It covers all 17
functional requirements, all 8 non-functional requirements, all 15 expected
behaviours, all 12 boundary conditions and all 9 invalid inputs. A summary:

| Specification section | Items | Covered by tests |
|---|---:|---|
| Functional requirements (FR) | 17 | 17 |
| Non-functional requirements (NFR) | 8 | 6 by test, 2 structural |
| Expected behaviours (B) | 15 | 15 |
| Boundary conditions (BC) | 12 | 12 |
| Invalid inputs (IN) | 9 | 9 (plus 2 unplanned exception cases) |

The two non-functional requirements marked "structural" are NFR-04 (standard
library only) and NFR-07 (adding a rule should mean adding a module, not editing
existing ones). Both are properties of how the code is shaped rather than how it
behaves, and I could not think of a runtime assertion that would genuinely prove
either. Rather than write a test that only looks like it covers them, I marked
them honestly as verified by inspection.

Building this matrix was not just paperwork. Going through it row by row is what
exposed the fact that two requirements had no test at all, which is covered in
section 5.6.

### Group 1 — Complexity counting

**What:** that a straight-line function scores 1 and each decision point adds
exactly 1.

**Why:** this is the only part of the tool that produces a number rather than a
yes/no. If the number is wrong by one, every threshold test downstream is also
wrong, but nothing crashes, so the bug is invisible unless something tests the
number directly.

**Defect prevented:** miscounting decision points. The two classic mistakes are
counting `if/else` as 2 (an `else` is the fall-through, not a decision) and
counting `a and b and c` as 1 instead of 2. I wrote tests for both because I
expected AI-generated code to get them wrong.

### Group 3 — Unused variables

**What:** mostly negative tests. A variable read later, a variable read only by a
nested closure, `x += 1`, an unused parameter, `_`, a loop target, a `with ... as`
target, tuple unpacking, a `global` declaration.

**Why:** this checker is the easiest one to make over-enthusiastic, and a checker
that reports variables you are actually using is worse than no checker at all —
people switch it off and then miss the real findings too.

**Defect prevented:** false positives from only looking at where names are stored
and forgetting they are also loaded somewhere else.

This group taught me something I had not expected. When I ran it against an empty
implementation, all the negative tests passed, because a checker that reports
nothing satisfies every "should not report" assertion. A suite made only of
negative tests would have looked completely green against code that did nothing.

### Group 5 — Duplicate code

**What:** identical blocks reported once, blocks differing only in variable names
still matching, three copies giving one issue with three locations, and the
boundary at exactly the minimum block size.

**Why:** this is the most algorithmically involved checker. It uses overlapping
sliding windows, so a genuinely duplicated ten-statement block matches at window
start 0, 1, 2, 3 and so on.

**Defect prevented:** duplicate reporting of duplicates. Without care, one
copy-paste produces seven near-identical warnings. The opposite bug also has to be
guarded against — de-duplicating too aggressively and hiding a second real
occurrence — which is why there is a test with three copies that checks all three
locations appear in one issue.

### Group 6 — Naming conventions

**What:** `calculateTotal` flagged, `calculate_total` clean, `my_class` flagged as
a class, `MyClass` and `HTTPServer` clean, `list` flagged as shadowing a built-in,
and `__init__`, `_private`, `MAX_SIZE`, `self`, `cls` and `i` all clean.

**Why:** the dunder case is the one that breaks a naive implementation. `__init__`
is not snake_case under a strict reading, but flagging it would fire on nearly
every class ever written.

**Defect prevented:** a regex that is either too strict (rejects `__init__`) or
too loose (accepts `calculateTotal`). This is exactly what happened, as described
in section 5.

### Group 10 — CLI

**What:** exit code 0 on clean input, 1 on input with issues, non-zero with a
usage message when no arguments are given.

**Why:** exit codes are part of the contract but are invisible in normal manual
use, so they only get checked if a test checks them.

**Defect prevented:** a CLI that finds problems, prints them, and then exits 0,
meaning a build would pass while the tool was actively reporting failures.

### Group 11 — Regression tests

These were added during development rather than designed up front, because you
cannot design a regression test for a bug you have not hit yet. Each is marked
with a comment saying which defect it locks down.

---

## 4. AI-Assisted Development Process

This section summarises the development session. The full log, including the exact
prompts and the terminal output at each stage, is in
`docs/ai-development-log.md`.

### 4.0 How I prompted, and how the prompts changed

The prompts were not the same shape all the way through. Looking back at them,
they changed in three specific ways as I learned what this AI was good and bad at.

**Every feature was split into two prompts, never one.** The first asks only for
tests, the second only for the implementation. This was deliberate: if you ask for
both at once, the AI writes tests that agree with the code it just decided to
write, and a test suite that agrees with the implementation by construction proves
nothing. Splitting them meant the tests were written against the specification
rather than against the code.

**The prompts got more specific about edge cases as the session went on.** My
iteration 1 prompt described the feature and listed the cases I wanted covered.
By iteration 4 I was naming the exact things that must *not* be reported:

> "Make sure `__init__`, `_helper`, `MAX_SIZE`, `HTTPServer`, `self`, `cls` and
> single letters like `i` are all treated as fine, because flagging any of those
> would make the tool useless."

That change was a direct response to what had gone wrong earlier. After the
nested-scope bug in iteration 1, I could see the pattern — the AI handles the case
you describe and does not think about the cases around it. So I started putting
the surrounding cases in the prompt rather than hoping for them. It worked
partially: the tests it generated in iteration 4 did cover `__init__`, but the
implementation it then wrote still failed them, which is how the regex bug was
caught.

**I started stating the failure mode rather than the feature.** The clearest
example is iteration 5, where the prompt was not "write a metrics module" but:

> "Tests first, and make sure the empty file and the file with no functions are
> covered — an average is a division."

Naming the specific way the code could break turned out to be far more effective
than describing what it should do. The same technique worked on the hardest part
of the project, the duplicate checker:

> "Make sure a six-statement duplicate is reported once as a six-statement block,
> not three times as overlapping four-statement blocks."

That prompt produced correct overlap handling on the first attempt. I am fairly
sure a prompt that just said "detect duplicate code" would not have.

**The limit of prompting.** What prompting could not fix is a blind spot shared
by both passes. When I asked for unused-import tests, the AI did not think of
`__all__` re-exports; when I then asked it to implement the checker, it did not
handle them either. Two separate prompts over the same problem, and the same
category missing from both. No wording I could have chosen would have helped,
because neither of us knew the case existed. It took running the tool against real
code to find it (section 5.6). That is the main thing prompt engineering cannot
do for you.

### 4.1 Iteration summary

### Iteration 1 — Cyclomatic complexity

**Feature:** score every function's complexity and report the ones over the
threshold.

**Prompt:** "Write `tests/test_complexity.py` first, using `unittest`. Cover a
straight-line function scoring 1, each decision type adding one, `else` adding
nothing, `a and b and c` counting as two decisions, methods getting qualified
names, nested functions scored separately, and the threshold boundary at exactly
10 versus 11."

**Red phase output:**

```
ModuleNotFoundError: No module named 'pyscan.analyzer'
Ran 1 test in 0.000s
FAILED (errors=1)
```

**Prompt:** "Now implement `pyscan/complexity.py` to satisfy those tests."

**AI response:** a recursive collector building dotted names for methods and
nested functions, plus a `_decision_points` function mapping node types to counts.
The counting itself was correct, including the boolean-operator case.

**Decision: modified.** The tree-walking helper had a real bug, described in
detail in section 5.1. One test failed, I fixed the walk, and the suite went
green at 21 tests.

### Iteration 2 — Unused variables and imports

**Prompt:** "Write the tests for unused locals and unused imports first. Include
negative cases: a variable read later, a variable read only by a nested closure,
`x += 1`, an unused parameter, `_`, a loop target, a `with ... as` target, tuple
unpacking, and a `global` declaration. For imports cover `import numpy as np`
being tracked under the alias, and `from x import *`."

**Red:** 8 failures out of 48 tests.

**AI response:** both checks, with the closure case handled correctly — it
collects reads from the whole subtree including nested functions, while collecting
assignments only from the function's own scope. Import aliasing was also right.

**Decision: accepted, then refactored.** No behavioural changes were needed. The
refactor was structural: `complexity.py` and `unused.py` had each grown their own
copy of the "walk this scope but stop at nested functions" logic, so I pulled it
out into a new `pyscan/astutils.py` along with the function collector. The
21 complexity tests from iteration 1 were the safety net that made me willing to
touch working code, and they all still passed afterwards. All 48 green.

### Iteration 3 — Duplicate code

**Prompt:** "Implement it with sliding windows over each list of consecutive
statements. Normalise variable names only. Make sure a six-statement duplicate is
reported once as a six-statement block, not three times as overlapping
four-statement blocks."

**AI response:** a fingerprinting function built on `ast.iter_fields` that blanks
out variable names while keeping everything else, plus a claim-based grouping pass
that takes the longest blocks first and marks their statements as used up.

**Decision: accepted.** This was the best AI output of the session. The overlap
handling was correct first time, which surprised me, because it was the part I had
least confidence in.

Three tests still failed, but all three were wrong tests rather than wrong code.
That is covered in section 5.5. 64 tests green.

### Iteration 4 — Naming conventions

**Prompt:** "Tests first. Make sure `__init__`, `_helper`, `MAX_SIZE`,
`HTTPServer`, `self`, `cls` and single letters like `i` are all treated as fine,
because flagging any of those would make the tool useless."

**Red:** 16 failures, 2 errors.

**Decision: modified.** Two separate problems with the generated code, both
described in section 5.2 and 5.3: the snake_case pattern rejected `_helper` and
`__init__`, and there was no handling of constants at all, so every `MAX_SIZE`
in a file got reported. I also rewrote the variable check to work per scope
rather than per file. 95 tests green.

### Iteration 5 — Code metrics

**Prompt:** "Tests first, and make sure the empty file and the file with no
functions are covered — an average is a division."

**Decision: modified.** The generated code computed `sum(scores) / len(scores)`
with no guard, so an empty file crashed. Section 5.4. 114 tests green.

### Iteration 6 — Public API and error handling

**Prompt:** "Tests first for every invalid-input row in the specification, plus a
determinism test that analyses the same source twice and compares the reports."

**Decision: accepted.** Straightforward. Worth noting that the determinism test
passed first time, but only because the duplicate checker sorts its output before
returning, which was a deliberate choice back in iteration 3 rather than luck. The
test now locks it in, so a `set` introduced later cannot quietly reintroduce
random ordering. 142 tests green.

### Iteration 7 — Command-line interface

**Prompt:** "Write `main` so it takes argv and the output streams as parameters
with defaults, so tests can call it directly with `StringIO` instead of spawning a
subprocess. Exit 0 for clean, 1 for issues found, 2 for a tool error."

**Decision: accepted, with one addition.** The generated version called
`parser.parse_args(argv)` without catching `SystemExit`. argparse raises that
itself on `--help` or a bad option, so a test calling `main(["--help"])` would
have had the exception escape instead of getting a return code back. I wrapped it.
163 tests green.

### Iteration 8 — Running PyScan on itself

Once everything passed I pointed the tool at its own source code. This was not
part of the plan and it turned out to be the most useful thing I did. It is
covered in section 5.6.

### Iteration 9 — Closing coverage gaps

Running coverage with branch coverage enabled gave 97%, and the misses pointed at
real holes: annotated assignments (`total: int = 0`) had never been tested at all,
`*args` and `**kwargs` parameters had never been tested, and several error paths
had no test. Adding those tests found one case I had not thought about, which is
in section 5.9. State at this point: 185 tests, 99% coverage.

### Iteration 10 — Traceability, and the requirements with no tests

**Prompt:** "Add tests for the requirements that currently have none. NFR-01
should prove no side effect happens when analysing code that would write a file if
it ran. FR-12 should check the fields on every issue produced by a messy source.
Also add NFR-05, the performance requirement. Then tag every test with the
requirement ID it covers and build a traceability matrix."

Building the matrix was what exposed the gap. The boundary conditions and invalid
inputs were all tagged, but the functional requirements were not, and two
requirements had no test at all — including NFR-01, that the tool must never
execute the code it analyses, which is the most important safety property in the
entire specification.

The NFR-01 and FR-12 tests passed immediately, which is the boring and correct
outcome. Writing the NFR-05 performance test is what uncovered the cubic memory
defect described in section 5.7, and fixing that produced a regression the
self-analysis test caught within seconds — my rewritten function came in at
complexity 12 against the limit of 10 the tool enforces. Splitting it into three
smaller functions brought it to 5.

**Final state:** 190 tests, all passing, 99% coverage.

### Evidence of test runs

The repository contains captured terminal output for each of these:

- `docs/evidence/test-run-verbose.txt` — the full verbose run of all 190 tests
- `docs/evidence/coverage-report.txt` — the coverage run and per-module table
- `docs/evidence/self-analysis.txt` — PyScan analysing its own source
- `docs/evidence/example-run.txt` — the tool run against a deliberately messy file

The commit history also follows the iterations, with one commit per feature.

---

## 5. Evaluation and Improvement of AI Output

This is the part of the assignment I found most interesting, because the AI's
mistakes were not random. They fell into a pattern: it was reliably good at the
main logic and reliably careless at the edges.

### 5.1 Bug — the nested-scope guard only checked children

The AI generated this helper, whose job is to walk a function's body while
skipping over any nested functions, so that an inner function's branches are not
counted against the outer one:

**Before:**

```python
def _walk_own_scope(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SCOPE_NODES):
            continue
        for descendant in _walk_own_scope(child):
            yield descendant
```

The guard only looks at *children*. But the caller passes in each statement of the
function body one at a time, so a nested `def` sitting directly in the body arrives
as `node` and is yielded before the guard ever runs. The whole nested function then
gets walked and its branches counted against the parent.

The test caught it straight away:

```
FAIL: test_nested_function_is_measured_separately
AssertionError: 3 != 2
```

**After:**

```python
def walk_own_scope(node):
    if isinstance(node, SCOPE_NODES):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from walk_own_scope(child)
```

Moving the check to the top fixes it and also removes the need for the manual
inner loop.

**Why this matters:** every other complexity test passed. The bug only appears
when a function contains a nested `def`, and it inflates the score of exactly the
functions most likely to be near the threshold already — long ones with helpers
inside them. Without a test aimed specifically at nesting, this would have shipped
and the tool would have been quietly wrong.

### 5.2 Incorrect assumption — the snake_case pattern rejected valid Python

The AI's first suggestion for the snake_case pattern was:

**Before:** `^[a-z][a-z0-9_]*$`

That demands a lowercase letter in the very first position, which rejects
`_helper` and `__init__`. Both are completely normal Python.

**After:** `^[a-z_][a-z0-9_]*$`

Allowing an underscore in the first position lets any number of leading
underscores through while still rejecting anything containing a capital letter.

**Why this matters:** this is a false positive that would fire on every private
function and every dunder method in a codebase. Nobody would use the tool for more
than a day.

### 5.3 Missing requirement — no handling of constants

The generated naming checker had no concept of a constant at all, so `MAX_SIZE = 10`
was reported as a snake_case violation. I added a second pattern:

```python
CONSTANT_CASE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
```

and accepted a name if it matches either pattern.

I also changed how variables are scoped. The generated version collected variable
names across the whole file in one pass, so the same badly named variable in two
different functions produced a single warning. I rewrote `_check_variables` to loop
over the module scope and each function scope separately:

```python
scopes = [tree] + [node for _, node in iter_functions(tree)]
```

Two people fixing two different functions need two warnings, not one.

### 5.4 Bug — division by zero on a file with no functions

**Before:**

```python
average_complexity=round(sum(scores) / len(scores), 2),
```

**After:**

```python
average_complexity=round(sum(scores) / len(scores), 2) if scores else 0.0,
comment_ratio=round(comment / documented, 3) if documented else 0.0,
```

The empty-file test caught this the moment it ran. This is the clearest example of
why writing the boundary conditions into the specification before any code existed
was worth the effort — BC-12 exists precisely because I predicted this, and the
prediction was right.

### 5.5 My own tests were wrong twice

Not everything that failed was the AI's fault. In iteration 3, three tests failed
against a correct implementation.

Two were line-number arithmetic:

```
FAIL: test_issue_is_reported_at_the_first_occurrence
AssertionError: Tuples differ: (8,) != (7,)
```

I had written 7 as the expected line. Counting the generated source properly —
`def first` on line 1, four statements on lines 2 to 5, a blank on line 6,
`def second` on line 7 — the second block actually starts on line 8. The tool was
right and I was wrong.

The third was more interesting:

```
FAIL: test_overlapping_occurrences_do_not_count_as_two
AssertionError: 0 != 1
```

My input was the statements `a, b, a, b, a` with a minimum block size of three, and
I had expected one duplicate. Working it through by hand, the only two matching
three-statement windows are positions 0–2 and 2–4, and they share the middle
statement. A block cannot be a duplicate of itself, so reporting nothing is
correct.

I rewrote the test to assert zero, and then added a second test using the *same
input* with a minimum of two, where `(a, b)` at lines 1 and 3 genuinely do not
overlap and one issue is the right answer:

```python
def test_overlapping_occurrences_do_not_count_as_two(self):
    source = "a = 1\nb = 2\na = 1\nb = 2\na = 1\n"
    self.assertEqual(duplicates(source, 3), ())

def test_the_same_source_does_report_when_the_pair_stops_overlapping(self):
    source = "a = 1\nb = 2\na = 1\nb = 2\na = 1\n"
    found = duplicates(source, 2)
    self.assertEqual(len(found), 1)
    self.assertEqual(found[0].related_lines, (3,))
```

Two tests over the same input pulling in opposite directions is much harder for a
broken implementation to satisfy than either test alone.

**Why this matters:** a green suite only means the code matches the tests. Both of
my mistakes came from doing arithmetic in my head instead of writing it down. This
is the honest limitation of TDD that does not usually get mentioned.

### 5.6 Missing test cases — found by running the tool on itself

After everything was green I ran PyScan over its own source:

```
$ python -m pyscan pyscan/*.py
pyscan/__init__.py
  7:UNU002  import 'analyze_file' is never used
  7:UNU002  import 'analyze_source' is never used
  ... (11 more of the same)
pyscan/cli.py
  28:CPX001  function 'main' has a cyclomatic complexity of 12,
             which is above the limit of 10
pyscan/duplication.py
  20:UNU002  import 'Tuple' is never used

15 issue(s) found in 13 file(s)
```

Three distinct findings, and importantly they were not all the same kind of thing.

**Finding 1 — a false positive (13 of the 15 issues).** Every re-export in
`__init__.py` was reported as unused. They are not unused; they are the package's
public interface, and the `__all__` list right underneath them says so
explicitly. None of my tests contained an `__all__`, and neither did any of the
AI-generated tests, so this whole category had never been exercised. The fix reads
a literal `__all__` and treats everything in it as used:

```python
def _exported_names(tree):
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
```

If `__all__` is built by code rather than written out as a literal, we cannot read
it, so the checker gives up quietly instead of guessing. There is a test for that
too.

**Finding 2 — a true positive.** `from typing import Tuple` in `duplication.py`
was left over from an earlier draft of the `_Window` class. Genuinely dead code,
and deleted.

**Finding 3 — a true positive against my own standard.** `cli.main` had a
complexity of 12, against the limit of 10 that the tool itself enforces. I split
it into `_or_default`, `_exit_code_of`, `_print_usage_error`, `_build_config`,
`_analyse_files` and `_analyse_one`, which brought it down to 7. The 163 existing
tests were what made that refactor safe, and all of them still passed afterwards.

I then promoted the whole exercise into a permanent test,
`tests/test_self_analysis.py`, which runs the analyser over its own package and
fails if a single issue is reported:

```python
def test_every_module_is_free_of_issues(self):
    for path in package_files():
        with self.subTest(module=os.path.basename(path)):
            report = analyze_file(path)
            described = [
                "%d:%s %s" % (issue.line, issue.rule_id, issue.message)
                for issue in report.issues
            ]
            self.assertEqual(described, [], "\n".join(described))
```

The analyser is now held to its own standard automatically, rather than whenever I
remember to check.

### 5.7 Design flaw — a correct algorithm that could not scale

This was the most serious problem found in the whole project, and it was not a
wrong answer. The duplicate checker produced correct output for every one of its
sixteen tests. The flaw was in the design.

Going back over the specification to build the traceability matrix, I noticed
NFR-05 (a 1000-line file analysed in well under a second) had no test. Before
writing one I benchmarked the tool to pick a sensible bound. The process was
killed by the operating system:

```
Exit code: 137          # SIGKILL
```

Re-running with smaller inputs showed why:

| Input | Time | Peak memory |
|---|---:|---:|
| 399 lines | 0.091 s | 78 MB |
| 599 lines | 0.255 s | 247 MB |
| 799 lines | 0.576 s | 587 MB |
| **999 lines** | **1.042 s** | **1257 MB** |
| 1199 lines | 1.749 s | 2033 MB |

A thousand-line file needed 1.26 GB and broke the one-second requirement. Memory
was growing cubically, which is why a larger file killed the process outright.

**The cause.** The generated design built every block of every length and stored
the *full structural text* of each block as a dictionary key:

```python
for size in range(min_size, len(statements) + 1):
    for start in range(len(statements) - size + 1):
        fingerprint = "\n".join(structures[start : start + size])
        by_fingerprint[fingerprint].append(_Window(...))
```

A block of 100 statements stores all 100 structures. The block starting one
statement later stores 99 of the same ones again. Each statement ends up copied
into roughly *n* different keys and there are roughly *n²/2* keys, so memory is
cubic in the file length. On the small snippets in the tests — none longer than
about a dozen statements — this is invisible.

**The fix**, in two parts:

1. Group blocks by a 128-bit hash of their structure rather than the structure
   text, extending a running hash one statement at a time. A block's fingerprint
   now costs one hash update instead of rebuilding an entire string.
2. Prune. If a block of a given length appears only once, then no longer block
   starting at that position can appear twice either — any match would have to
   match the shorter block first. So a candidate with no partner is dropped and
   never grown again. In ordinary code almost everything is unique after two or
   three statements, so nearly all candidates die in the first round.

```python
while live:
    size += 1
    buckets = _grow_candidates(live, structures, size)
    live = {}
    for fingerprint, entries in buckets.items():
        if len(entries) < 2:
            continue  # unique now, so unique at every greater size too
        live.update(entries)
        if size >= min_size:
            _record(by_fingerprint, fingerprint, size, entries, sequences)
```

**Result:**

| Input | Before | After |
|---|---|---|
| 999 lines | 1.042 s / 1257 MB | 0.074 s / 15 MB |
| 1999 lines | (not measured — too slow) | 0.148 s / 18 MB |
| 3999 lines | (process killed) | 0.299 s / 26 MB |
| 7999 lines | (process killed) | 0.616 s / 40 MB |

At the 1000-line mark that is 14 times faster using 85 times less memory, and the
growth is linear rather than cubic. An 8000-line file that the old version could
not finish at all now takes under a second.

**All sixteen duplicate-detection tests passed unchanged.** That is the part I
want to highlight. I rewrote the core of the most complicated component in the
project, and the existing tests told me within half a second that the behaviour
was identical. Without them I would not have attempted the rewrite at all, because
I would have had no way to tell a faster implementation from a subtly broken one.

**Why the tests missed it.** Every duplicate-detection test used a snippet of
about a dozen statements, which is the right size for checking logic and useless
for checking scale. The defect only exists at a size no test ever used. This is
the clearest lesson of the project for me: functional tests confirm the code gives
the right answer, and say nothing at all about whether it can give that answer on
real input. The non-functional requirements needed their own tests, and until I
wrote the traceability matrix I had not noticed they did not have any.

### 5.8 Design flaw — the wrong scoping model

A smaller design-level problem, from iteration 4. The generated naming checker
collected variable names across the whole file in a single pass:

```python
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        ...
```

That is not just an implementation detail, it is the wrong model of the problem.
Variables live in scopes, and the same badly named variable in two different
functions is two problems for two people to fix. Walking the whole tree flattens
that away and reports one issue.

**After:**

```python
scopes = [tree] + [node for _, node in iter_functions(tree)]
for scope in scopes:
    for name, line in sorted(plain_assignments(scope).items(), ...):
```

The fix required a test that did not exist yet
(`test_the_same_bad_name_in_two_scopes_is_reported_twice`), because the original
AI-generated tests all used single-function examples and so could not tell the two
models apart.

### 5.9 One more gap found by coverage

Adding tests for annotated assignments turned up a case I had not thought about.
`self.total: int = 0` is an annotated assignment whose target is an *attribute*,
not a plain name, so it must not be treated as a local variable. The code already
handled it correctly by accident, but there was no test proving it, so I added
one.

One reported coverage miss turned out to be an artifact rather than a real gap.
Coverage flagged a bare `continue` as never executed, which could not be true given
how often that branch runs — CPython optimises the jump and the line never gets
traced. Rather than leave a confusing red line, I restructured the function to
return early from a small helper. That removed the `continue` entirely and made
the function easier to read, which was worth doing anyway.

### 5.10 Summary of the pattern

| Kind of problem | Count | Where the AI struggled |
|---|---:|---|
| Logic bug in generated code | 2 | Recursion base cases; guards applied at the wrong level |
| Missing edge-case handling | 3 | Division by zero, constants, uncaught `SystemExit` |
| Too-strict pattern (false positives) | 1 | Regex that rejected `__init__` and `_helper` |
| Design flaw — does not scale | 1 | Cubic memory in the duplicate checker |
| Design flaw — wrong model | 1 | File-wide instead of per-scope variable naming |
| Missing test category entirely | 1 | `__all__` re-exports — absent from AI tests *and* mine |
| My own faulty tests | 3 | Line-number arithmetic and overlap reasoning |

Two things stand out. The AI was consistently good at the main path of an
algorithm and consistently careless at the edges, which is close to the opposite
of where I would have guessed the risk was before starting. And the two most
serious problems — the cubic memory and the wrong scoping model — were not bugs
at all in the usual sense. Both produced correct output on every input anyone had
tried. They were bad designs that happened to give right answers at small scale,
and no amount of reading the code carefully would have surfaced the first one.
Only running it on something big did.

---

## 6. Testing Results

### 6.1 Test suite

All 190 tests pass.

```
$ python -m unittest discover -s tests -t .
..........................................................................
..........................................................................
..........................................
----------------------------------------------------------------------
Ran 190 tests in 1.212s

OK
```

| Test module | Tests | Covers |
|---|---:|---|
| `test_analyzer.py` | 37 | Public API, ordering, determinism, config, errors, file I/O, non-functional guarantees |
| `test_unused.py` | 36 | Unused locals and imports, `__all__` handling |
| `test_naming.py` | 32 | All five naming rules |
| `test_cli.py` | 26 | Options, output, exit codes, `python -m pyscan` |
| `test_complexity.py` | 21 | Complexity counting, scoping, threshold boundary |
| `test_metrics.py` | 19 | Line counts, structure counts, averages, ratios |
| `test_duplication.py` | 16 | Structural matching, overlap handling, boundaries |
| `test_self_analysis.py` | 3 | PyScan analysing its own source |
| **Total** | **190** | |

Within that, the suite covers all 12 boundary conditions and all 9 invalid inputs
from the specification, plus 2 exception cases the specification did not predict
(a non-UTF-8 file and an unreadable file), and 12 named regression tests. Those
regression tests are listed individually in `docs/test-design.md` section 3, each
against the defect it locks down:

| Regression test | Defect it prevents returning |
|---|---|
| `test_nested_function_is_measured_separately` | Nested `def` branches counted against the parent |
| `test_names_listed_in_dunder_all_count_as_used` | Re-exports reported as unused imports |
| `test_dunder_method_is_clean` | A regex that rejected `__init__` and `_helper` |
| `test_upper_case_constant_is_clean` | Every `MAX_SIZE` reported as a naming violation |
| `test_empty_file_does_not_divide_by_zero` | Crash on a file with no functions |
| `test_a_thousand_line_file_is_analysed_in_well_under_a_second` | The cubic memory blow-up in section 5.7 |
| `test_no_module_exceeds_the_default_complexity_limit` | The tool drifting past its own limit |
| `test_every_module_is_free_of_issues` | Any regression the tool can detect in its own source |

(The table shows eight; the remaining four are variations covering the same
defects with different input shapes, such as `__all__` written as a tuple or built
dynamically.)

The tail of the verbose run, captured in `docs/evidence/test-run-verbose.txt`:

```
test_variable_read_inside_a_branch_is_not_reported (tests.test_unused.TestUnusedLocalVariables) ... ok
test_variable_that_is_read_later_is_not_reported (tests.test_unused.TestUnusedLocalVariables) ... ok
test_variable_used_only_by_a_nested_function_is_not_reported (tests.test_unused.TestUnusedLocalVariables) ... ok
test_with_statement_target_is_not_reported (tests.test_unused.TestUnusedLocalVariables) ... ok

----------------------------------------------------------------------
Ran 190 tests in 0.537s

OK
```

### 6.2 Coverage

Measured with `coverage` 7.10.7, with branch coverage enabled:

```
Name                    Stmts   Miss Branch BrPart  Cover
----------------------------------------------------------
pyscan/__init__.py          6      0      0      0   100%
pyscan/__main__.py          4      4      2      0     0%
pyscan/analyzer.py         49      0      6      0   100%
pyscan/astutils.py         47      0     26      0   100%
pyscan/cli.py              80      0     16      0   100%
pyscan/complexity.py       30      0     10      0   100%
pyscan/config.py           27      0     10      0   100%
pyscan/duplication.py     108      0     42      0   100%
pyscan/errors.py            8      0      0      0   100%
pyscan/metrics.py          19      0      6      0   100%
pyscan/models.py           35      0      0      0   100%
pyscan/naming.py           64      0     28      0   100%
pyscan/unused.py           72      0     48      0   100%
----------------------------------------------------------
TOTAL                     549      4    194      0    99%
```

Every module is at 100% except `__main__.py`. That file is a four-line entry point
whose body only runs when Python is invoked as `python -m pyscan`, which happens in
a subprocess where the coverage tool is not watching. It *is* tested — there are
two subprocess tests confirming the module returns the right exit codes for clean
and messy input — but that execution does not show up in the numbers. I decided to
leave it visible and explain it rather than add an `omit` rule to make the report
say 100%, since that would have been hiding something rather than fixing it.

The same run also produces an HTML report in `htmlcov/`, which is what I used while
working to see exactly which branches were still uncovered.

### 6.3 Self-analysis

The analyser reports no issues on its own source:

```
$ python -m pyscan pyscan/*.py
...
no issues found in 13 file(s)
```

Exit code 0.

### 6.4 Performance

NFR-05 asks for a 1000-line file in well under a second. After the rewrite
described in section 5.7:

```
 100 functions (  399 lines):   0.031 s   peak RSS    12.5 MB
 250 functions (  999 lines):   0.074 s   peak RSS    14.8 MB
 500 functions ( 1999 lines):   0.148 s   peak RSS    18.0 MB
1000 functions ( 3999 lines):   0.299 s   peak RSS    25.6 MB
2000 functions ( 7999 lines):   0.616 s   peak RSS    39.7 MB
```

Time is linear in file size and memory is close to flat. The requirement is met
with about thirteen times of headroom at the 1000-line mark, and
`test_a_thousand_line_file_is_analysed_in_well_under_a_second` now fails the build
if that stops being true.

### 6.5 The tool working on real input

Run against a deliberately messy file (`examples/example.py`):

```
$ python -m pyscan examples/example.py
examples/example.py
  4:UNU002  import 'os' is never used
  7:NAM001  function 'calculateTotal' should be named in snake_case
  7:NAM004  argument 'userName' should be named in snake_case
  8:NAM002  variable 'unusedValue' should be named in snake_case
  8:UNU001  variable 'unusedValue' is assigned in 'calculateTotal' but never used
  12 lines (7 code, 2 comment, 3 blank), 1 functions, 0 classes, average complexity 2.00, highest complexity 2

5 issue(s) found in 1 file(s)
exit code: 1
```

Note that `unusedValue` correctly produces two separate issues — it is both badly
named and unused — and that the exit code is 1, as FR-16 requires.

---

## 7. Reflection

### How AI contributed

The honest answer is that AI made me much faster at the parts I already understood
and roughly the same speed at the parts I did not. Writing out a naming checker
with five rules, or the argparse wiring for a CLI with five options, is work I
could do but it would have taken an afternoon each. The AI produced those in
seconds and they were about 90% right.

Where it helped most was the boring, high-volume work: generating the first
version of a test module from a description of what to cover, writing the
docstrings, and handling the fiddly parts of the `ast` API that I would otherwise
have had to look up repeatedly. It knew, for example, that `import a.b.c` binds
the name `a` and not `a.b.c`, which is the kind of detail I would probably have got
wrong on the first try.

### Where AI performed well

The single best output was the duplicate-code checker. I asked it to handle the
overlapping-windows problem and it produced a claim-based approach — sort the
groups longest-first, and mark statements as used up once they have been reported
— that worked correctly on the first run. That is the most complicated piece of
logic in the project and it was the piece that needed the fewest corrections.

It was also good at the main path of every algorithm. Counting decision points for
complexity, tracking import aliases, walking the tree to find reads and writes:
all of that was right first time. Notably it got `a and b and c` counting as two
decisions rather than one, which was a mistake I had specifically written a test
for because I expected it to fail.

### Where AI produced incorrect or incomplete results

The failures were all at the edges, and they had a common shape: the AI wrote code
for the case it was thinking about and did not consider the cases around it.

The nested-scope guard is the clearest example. It correctly understood that
nested functions should be skipped, and it wrote a check that skips them — but it
put the check on the children rather than at the entry point, so it missed the one
arrangement where a nested `def` is the first thing it sees. The intent was right
and the implementation was subtly wrong in a way that reads perfectly well.

The snake_case regex is the same shape of mistake. It wrote a pattern that
correctly describes snake_case in the abstract, without thinking about the
real-world names that would be run through it. The missing division-by-zero guard,
the missing constant pattern and the uncaught `SystemExit` are all the same thing:
the happy path, done well, with nothing around it.

The most instructive failure was the `__all__` one, because it was invisible. The
AI did not write anything wrong; it wrote a checker for the case it was asked
about. But when I asked it to generate tests for unused imports, it did not think
of `__all__` either — and neither did I. Two passes over the same problem, by two
different kinds of reasoning, and the same category was missed both times. Only
running the tool against real code exposed it.

### Lessons about test-driven development

**Writing the test first genuinely changes the design.** The clearest case is
`main(argv, stdout, stderr)`. I only gave `main` those parameters because I was
thinking about how to test it, and that made the CLI tests fast, readable and
completely free of monkey-patching. If I had written the CLI first and then tried
to test it, I would have ended up with subprocess tests that are slower and tell
you less when they fail.

**Boundary conditions are worth writing down before you code.** BC-12 (average
complexity of a file with no functions) exists in the specification because I
predicted the AI would forget the guard. It did. Predicting the failure and
writing the test before seeing the code was more effective than reviewing the code
afterwards would have been, because when I read code I tend to read it the way the
author intended it rather than looking for what is missing.

**A green suite is not proof of correctness.** This is the thing I actually learned
rather than just repeated from the tutorial. My own tests were wrong twice, and
both times I trusted my arithmetic over the tool's output for a few minutes before
working it through properly. Tests are code, and code has bugs.

**Negative tests alone prove nothing.** When I ran the unused-variable tests
against an empty implementation, every "should not report" test passed. Any suite
made mostly of negative assertions can look healthy against code that does
nothing at all. Every rule needs at least one test that fails when the rule is
switched off.

**Passing tests say nothing about whether the code can scale.** This is the
lesson I did not expect. The duplicate checker passed all sixteen of its tests and
was still unusable on any real file, because every test snippet was about a dozen
statements long and the defect only appears at a few hundred. A test suite tells
you the code produces the right answer on the inputs you chose. It has no opinion
at all about whether it can produce that answer on the inputs your users have.
The only reason I found it is that I went looking for a number to put in a
performance test.

**Non-functional requirements need tests too, or they are just wishes.** I wrote
eight non-functional requirements in the specification and then tested almost none
of them for most of the project. NFR-05 was violated by a factor of well over a
hundred on memory and nobody would have known. NFR-01 — that the tool must never
execute the code it analyses — is the single most important safety property in the
whole specification, and it had no test at all until the last iteration. It
happened to be true, but "happens to be true" and "is guaranteed" are different
things, and only one of them survives someone else editing the code.

**Refactoring only feels safe when the tests already exist.** I pulled shared
helpers into `astutils.py` in iteration 2, split `cli.main` in iteration 8, and
rewrote the entire core of the duplicate checker in iteration 10. That last one is
the strongest case: I replaced the most complicated algorithm in the project, and
the existing tests told me in half a second that the behaviour was identical. I
would not have attempted it otherwise, because I would have had no way to tell a
faster implementation from a subtly broken one. Without tests, the rational choice
is always to leave bad code alone, and that is exactly how codebases rot.

### How the testing strategy improved the software

Concretely, seven defects were caught and fixed that would otherwise have shipped:
the nested-scope complexity bug, the regex rejecting `__init__`, the missing
constant handling, the file-wide instead of per-scope variable naming, the
division by zero on empty files, the uncaught `SystemExit`, and the cubic memory
use in the duplicate checker. Every one was found by running something — a test or
the tool itself — rather than by reading the code. I read all of this code, some
of it several times, and found none of them that way.

Less obviously, the testing changed the shape of the code. Because each checker had
to be testable on its own, each one ended up in its own module with a single
`check(context)` entry point. That is why adding a new rule now means adding one
file and one line to a tuple, rather than editing anything that already works.

The self-analysis test is the part I am happiest with. It turns the tool into its
own quality gate, and it found three real problems the moment I wrote it —
including one in my own code that I would have defended if a person had raised it.

### What I would improve with more time

**Multi-file analysis.** Right now every check stops at the file boundary, which
means a function that nothing in the whole project calls still looks used if it is
called from within its own file. Doing this properly needs an import graph and a
way to resolve names across modules, which is a significant piece of work.

**Property-based testing.** All my tests use examples I chose, which means they
only cover cases I thought of — and section 5.6 is a direct demonstration that the
cases I did not think of are the dangerous ones. Generating random valid Python
and asserting invariants (analysis never crashes; the same input always gives the
same output; issue line numbers are always within the file) would explore inputs I
would never write by hand.

**Configuration from a file.** Real linters read a `setup.cfg` or `pyproject.toml`.
Passing `--disable` on the command line every time is fine for one file and
annoying for a project.

**A `# noqa`-style escape hatch.** Sometimes a rule is genuinely wrong for one
specific line, and there is currently no way to say so except turning the whole
rule off. Every real linter has this and it is a notable gap.

**Better duplicate reporting.** The checker tells you a block is duplicated and
gives you the line numbers, but it does not show you the block. Printing the
matched code, or at least the first line of it, would make the output far more
useful.

**Testing against a larger real codebase.** Running PyScan over its own 519
statements found three issues. Running it over something substantial would almost
certainly find more false positives, and false positives are the thing that decides
whether a tool like this gets used or ignored.

---

## 8. References

- Charles Darwin University, PRT582 Software Engineering: Process and Tools,
  *Tutorial 3: Test Driven Development*. Used for the red-green-refactor workflow,
  the `unittest` structure and the `test_` file naming convention.
- Python Software Foundation, *ast — Abstract Syntax Trees*, Python 3.9 standard
  library documentation. Used for the node types and the tree-walking API.
- Python Software Foundation, *unittest — Unit testing framework*, Python 3.9
  standard library documentation.
- van Rossum, G., Warsaw, B. and Coghlan, N., *PEP 8 — Style Guide for Python
  Code*. Used as the basis for the naming rules (NAM001–NAM004).
- Ned Batchelder, *Coverage.py* documentation. Used for branch coverage
  measurement and the HTML report.

---

## Appendix A — Repository contents

```
pyscan/                     the application (13 modules, 549 statements)
tests/                      the test suite (8 modules, 190 tests)
examples/example.py         a deliberately messy file for demonstration
docs/
  specification.md          requirements, written before any code
  test-design.md            the eleven test groups and why each exists
  ai-development-log.md     the AI-TDD session as it happened
  evidence/                 captured terminal output
README.md                   installation and usage
requirements.txt            coverage==7.10.7 (development only)
```

## Appendix B — Reproducing the results

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m unittest discover -s tests -t .

coverage run --branch --source=pyscan -m unittest discover -s tests -t .
coverage report -m
coverage html

python -m pyscan pyscan/*.py
python -m pyscan examples/example.py
```
