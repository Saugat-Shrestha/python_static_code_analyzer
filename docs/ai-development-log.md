# AI-Assisted Development Log

A running record of the AI-TDD session, written as it happened rather than
reconstructed afterwards. Prompts are recorded as they were issued in Cursor.
Where a follow-up was just "continue" or "yes", it has been folded into the
previous entry rather than listed separately.

For every feature the loop was the same:

1. Write the test first and run it, expecting failure (**red**).
2. Prompt the AI for an implementation.
3. Run the tests again (**green**), or fix whatever broke.
4. Refactor, and re-run to confirm nothing regressed.

---

## Iteration 0 — Specification and test design

**Prompt:** "Before writing any code, produce a specification for a Python
static code analyser covering functional and non-functional requirements,
assumptions, constraints, at least ten expected behaviours, boundary conditions
and invalid input scenarios. Then design the test suite and explain what each
test group is for."

**AI response summary:** Produced `docs/specification.md` and
`docs/test-design.md`. The requirements table and the eleven test groups came
out well. The first draft of the boundary conditions was thin — it listed the
complexity threshold and the empty file, but nothing about division by zero.

**Decision: modified.** I added BC-12 (average complexity of a file with zero
functions) because `total / count` is the obvious way to write an average and it
crashes on an empty file. I also added BC-08 (`_` should never be reported as
unused), since that is a convention the AI had not mentioned and a checker that
flags `_` would be noisy on real code.

---

## Iteration 1 — Cyclomatic complexity (CPX001)

**Feature:** score every function's cyclomatic complexity and report the ones
over the threshold.

**Prompt:** "Write `tests/test_complexity.py` first, using `unittest`. Cover a
straight-line function scoring 1, each decision type adding one, `else` adding
nothing, `a and b and c` counting as two decisions, methods getting qualified
names, nested functions scored separately, and the threshold boundary at exactly
10 versus 11."

**Red phase:**

```
ModuleNotFoundError: No module named 'pyscan.analyzer'
Ran 1 test in 0.000s
FAILED (errors=1)
```

**Prompt:** "Now implement `pyscan/complexity.py` to satisfy those tests."

**AI response summary:** Generated a recursive collector that builds dotted
names for methods and nested functions, plus a `_decision_points` function
mapping node types to counts. The counting logic itself was correct, including
the `BoolOp` case (`len(node.values) - 1`), which is the one I expected it to get
wrong.

**Decision: modified.** The generated `_walk_own_scope` had a real bug. It was
written to skip nested functions like this:

```python
def _walk_own_scope(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SCOPE_NODES):
            continue
        for descendant in _walk_own_scope(child):
            yield descendant
```

The guard only looks at *children*. But `_score` calls this function on each
statement in the body, so a nested `def` that sits directly in the body is passed
in as `node` and yielded before the guard ever runs — meaning the whole nested
function gets walked and its branches counted against the parent.

The test caught it immediately:

```
FAIL: test_nested_function_is_measured_separately
AssertionError: 3 != 2
```

Fix — move the check to the top of the function, which also removes the need for
the manual inner loop:

```python
def _walk_own_scope(node):
    if isinstance(node, SCOPE_NODES):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_own_scope(child)
```

**Why this matters:** the bug only shows up when a function contains a nested
`def`. Every other test passed. Without a test aimed specifically at nesting,
this would have shipped, and it inflates the score of exactly the functions most
likely to be near the threshold already — long ones with helpers inside them.

**Green:**

```
Ran 21 tests in 0.004s
OK
```

---

## Iteration 2 — Unused variables and imports (UNU001, UNU002)

**Feature:** report local variables that are assigned and never read, and
imports that are never used.

**Prompt:** "Write the tests for unused locals and unused imports first. Include
negative cases: a variable read later, a variable read only by a nested closure,
`x += 1`, an unused parameter, `_`, a loop target, a `with ... as` target, tuple
unpacking, and a `global` declaration. For imports cover `import numpy as np`
being tracked under the alias, and `from x import *`."

**Red:** 8 failures out of 48 tests. The negative tests passed straight away
because a checker that reports nothing passes every "should not report" test —
worth noticing, since a suite of only negative tests would have looked green
against an empty implementation.

**Prompt:** "Implement `pyscan/unused.py`. Be conservative: only plain
`name = value` assignments count, because reporting a variable someone is
actually using is worse than missing one."

**AI response summary:** Produced both checks. The closure case was handled
correctly (it collects reads from the whole subtree including nested functions,
while collecting assignments only from the function's own scope). The alias
handling for `import a.b.c` versus `import x as y` was also right.

**Decision: accepted, then refactored.** No behavioural changes were needed.
The refactor was structural: `complexity.py` and `unused.py` had both grown their
own copy of the "walk this scope but stop at nested functions" logic and their
own function collector, so I moved `walk_own_scope`, `own_scope_nodes`,
`iter_functions` and `parameter_names` into a new `pyscan/astutils.py`.

The complexity tests from iteration 1 were the safety net for that move — the
whole point of having them. All 48 tests passed afterwards, which is the only
reason I was willing to touch working code.

---

## Iteration 3 — Duplicate code (DUP001)

**Feature:** find blocks of structurally identical consecutive statements.

**Prompt:** "Write the tests for duplicate detection first. Cover two identical
blocks reported once, blocks that differ only in variable names still matching,
`data.append` versus `data.remove` *not* matching, three copies giving one issue
with three locations, and the boundary at exactly the minimum block size."

**Red:** 8 failures, 2 errors.

**Prompt:** "Implement it with sliding windows over each list of consecutive
statements. Normalise variable names only. Make sure a six-statement duplicate
is reported once as a six-statement block, not three times as overlapping
four-statement blocks."

**AI response summary:** Produced a fingerprinting function built on
`ast.iter_fields` that blanks out `Name.id` and `arg.arg` while keeping
everything else, plus a claim-based grouping pass that takes the longest blocks
first and marks their statements as used up.

**Decision: accepted.** This was the best AI output of the session. The
overlap handling was correct first time, which surprised me, because it is the
part I had least confidence in.

**But three tests still failed — and all three were wrong tests, not wrong code.**

```
FAIL: test_issue_is_reported_at_the_first_occurrence
AssertionError: Tuples differ: (8,) != (7,)
```

I had written the expected line number as 7. Counting the generated source
properly — `def first` on line 1, four statements on lines 2 to 5, a blank line
6, `def second` on line 7 — the second block actually starts on line 8. The tool
was right and I was wrong.

The third failure was more interesting:

```
FAIL: test_overlapping_occurrences_do_not_count_as_two
AssertionError: 0 != 1
```

My input was `a, b, a, b, a` with a minimum block size of three, and I had
expected one duplicate. Working through it by hand: the only two matching
three-statement windows are positions 0-2 and 2-4, and they share the middle
statement. A block cannot be a duplicate of itself, so reporting nothing is
correct. I rewrote the test to assert zero, and added a second test using the
*same input* with a minimum of two, where `(a, b)` at lines 1 and 3 genuinely
do not overlap and one issue is correct.

**Why this matters:** this is the failure mode people warn about with TDD — a
green suite only means the code matches the tests, and a test can be confidently
wrong. Both of my mistakes were arithmetic I had done in my head instead of on
paper. Splitting the overlap test into two cases that pull in opposite
directions makes it much harder for a broken implementation to satisfy both.

**Green:** 64 tests, all passing.

---

## Iteration 4 — Naming conventions (NAM001-NAM005)

**Feature:** snake_case, PascalCase and built-in shadowing checks.

**Prompt:** "Tests first. Make sure `__init__`, `_helper`, `MAX_SIZE`,
`HTTPServer`, `self`, `cls` and single letters like `i` are all treated as
fine, because flagging any of those would make the tool useless."

**Red:** 16 failures, 2 errors.

**Prompt:** "Now implement `pyscan/naming.py`."

**AI response summary:** The first regex it offered for snake_case was
`^[a-z][a-z0-9_]*$`.

**Decision: modified.** That pattern rejects `_helper` and `__init__`, because
it demands a lowercase letter in the first position. I changed the character
class to `^[a-z_][a-z0-9_]*$`, which allows any number of leading underscores
while still rejecting anything with a capital letter in it. I also added
`CONSTANT_CASE` so that `MAX_SIZE = 10` is accepted, which the AI had not
included at all — its version reported every constant in the file.

I kept its `PASCAL_CASE` pattern (`^_?[A-Z][a-zA-Z0-9]*$`) because it correctly
accepts `HTTPServer` while rejecting `Foo_Bar`.

The other change I made was scoping. The generated version collected variable
names across the whole file in one pass, so the same bad name in two different
functions produced one warning. I rewrote `_check_variables` to loop over the
module scope and each function scope separately, because two people fixing two
functions need two warnings.

**Green:** 95 tests, all passing.

---

## Iteration 5 — Code metrics

**Feature:** line counts, function and class counts, average and maximum
complexity, comment ratio.

**Prompt:** "Tests first, and make sure the empty file and the file with no
functions are covered — an average is a division."

**AI response summary:** The generated `calculate_metrics` computed
`sum(scores) / len(scores)` with no guard.

**Decision: modified.** I added the `if scores else 0.0` guard on the average
and the same treatment for `comment_ratio`. The empty-file test (BC-12) caught
this the moment it ran, which is exactly why it was written into the
specification before any code existed.

**Green:** 114 tests, all passing.

---

## Iteration 6 — Public API and error handling

**Feature:** `analyze_file`, path errors, ordering, determinism, configuration
validation.

**Prompt:** "Tests first for every invalid-input row in the specification, plus
a determinism test that analyses the same source twice and compares the reports."

**AI response summary:** Straightforward, and accepted as generated.

**Decision: accepted.** One thing worth noting is that the determinism test
(NFR-02) passed first time, but only because the duplicate checker sorts its
output before returning. That was a deliberate design choice from iteration 3
rather than luck, and the test now locks it in — a `set` introduced later
cannot quietly reintroduce random ordering.

**Green:** 142 tests, all passing.

---

## Iteration 7 — Command-line interface

**Feature:** the CLI, its options, its output and its exit codes.

**Prompt:** "Write `main` so it takes argv and the output streams as parameters
with defaults, so tests can call it directly with `StringIO` instead of
spawning a subprocess. Exit 0 for clean, 1 for issues found, 2 for a tool
error."

**AI response summary:** Generated the argparse setup and the printing helpers.

**Decision: accepted, with one addition.** The generated version called
`parser.parse_args(argv)` without catching `SystemExit`. argparse raises that
by itself on `--help` or a bad option, so a test calling `main(["--help"])`
would have had the exception escape rather than getting a return code. I wrapped
it and converted the exit request into a return value.

**Green:** 163 tests, all passing.

---

## Iteration 8 — Running PyScan on itself

Once everything passed I pointed the tool at its own source. This was not part
of the plan and it turned out to be the most useful thing I did all session.

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

Three distinct findings, and they were not all the same kind of thing.

**Finding 1 — a false positive (13 of the 15 issues).** Every re-export in
`__init__.py` was reported as unused. They are not unused; they are the package's
public interface, and `__all__` right underneath them says so. None of my tests
had a `__all__` in them, so nothing had ever exercised this. Fix: `_exported_names`
reads a literal `__all__` and treats everything in it as used. If `__all__` is
built by code we cannot read it, so the checker gives up quietly instead of
guessing — there is a test for that too.

**Finding 2 — a true positive.** `from typing import Tuple` in `duplication.py`
was left over from an earlier draft of the `_Window` class. Genuinely dead, and
deleted.

**Finding 3 — a true positive against my own standard.** `cli.main` had a
complexity of 12 against the limit of 10 that the tool itself enforces. I
extracted `_or_default`, `_exit_code_of`, `_print_usage_error`, `_build_config`,
`_analyse_files` and `_analyse_one`, bringing it down to 7. The 163 tests that
already existed were what made that refactor safe, and they all still passed
afterwards.

**Decision:** all three fixed, and the whole exercise promoted into a permanent
test, `tests/test_self_analysis.py`, which runs the analyser over its own package
and fails if a single issue is reported. The tool is now held to its own standard
automatically instead of whenever I remember to check.

---

## Iteration 9 — Coverage gaps

Running `coverage` with branch coverage on gave 97%, and the misses pointed at
real holes rather than trivia:

- Annotated assignments (`total: int = 0`) were never tested at all, in either
  the unused-variable checker or the naming checker.
- `*args` and `**kwargs` parameters were never tested.
- The `UnicodeDecodeError` and `OSError` paths in `read_source` had no test.
- `--help` and unknown-option handling in the CLI had no test.
- Non-string entries inside `__all__` had no test.

I added tests for each. One of them found a case I had not thought about:
`self.total: int = 0` is an annotated assignment whose target is an attribute,
not a name, and it must not be treated as a local variable.

One reported miss turned out to be an artifact rather than a gap. Coverage
flagged a bare `continue` in `plain_assignments` as never executed, which cannot
be true given how often that branch is taken — CPython optimises the jump and
the line never gets traced. Rather than leave a confusing red line in the
report, I restructured the function to return early from a small
`_assigned_names` helper. That removed the `continue` entirely and made the
function easier to read, which was worth doing on its own merits.

**State at this point:** 185 tests, all passing, 99% coverage. The only uncovered file is
`__main__.py`, which is a four-line entry point that only ever executes inside a
subprocess, where the coverage tool is not watching. It *is* tested — there are
two subprocess tests confirming `python -m pyscan` returns the right exit codes —
but that execution does not show up in the coverage numbers.

---

## Iteration 10 — Testing the non-functional requirements

Going back over the specification I realised the traceability was one-sided. The
boundary conditions and invalid inputs were all tagged in the tests, but the
functional requirements were not, and two requirements had no test at all:

- **NFR-01**, that the tool must never execute the code it analyses. This is the
  most important safety property in the whole specification and there was nothing
  checking it.
- **FR-12**, that every issue carries a rule ID, a line, a message and a severity.

**Prompt:** "Add tests for the requirements that currently have none. NFR-01
should prove no side effect happens when analysing code that would write a file
if it ran. FR-12 should check the fields on every issue produced by a messy
source. Also add NFR-05, the performance requirement."

Both new tests passed straight away, which is the boring outcome. The performance
test was a different story.

### The performance defect

Before writing the NFR-05 test I benchmarked the analyser to pick a sensible
bound. The first run was killed by the operating system:

```
$ python benchmark.py
(no output)
Exit code: 137          # SIGKILL
```

It had produced no output at all because stdout was still buffered when the
process was killed. Re-running with smaller inputs and explicit flushing showed
what was happening:

```
100 functions ( 399 lines):   0.091 s   peak RSS    77.6 MB
150 functions ( 599 lines):   0.255 s   peak RSS   247.0 MB
200 functions ( 799 lines):   0.576 s   peak RSS   586.7 MB
250 functions ( 999 lines):   1.042 s   peak RSS  1256.7 MB
300 functions (1199 lines):   1.749 s   peak RSS  2033.3 MB
```

A thousand-line file took 1.26 GB of memory. NFR-05 says a file that size should
be analysed in well under a second, so this was a straight requirement violation,
and the growth was cubic — which is why 800 functions got killed.

**Cause.** The duplicate checker built every block of every length from
`min_size` upwards and stored the *full structural text* of each one as a
dictionary key. A block of 100 statements stores all 100 statement structures;
the block starting one statement later stores 99 of those same structures again.
Every statement ends up copied into roughly `n` different keys, and there are
roughly `n²/2` keys, so the memory is cubic in the length of the file.

**Fix.** Two changes, both in `_windows_by_fingerprint`:

1. Group blocks by a 128-bit hash of their structure instead of the structure
   text. The running hash is extended one statement at a time, so a block's
   fingerprint costs one hash update rather than rebuilding the whole string.
2. Prune aggressively. If a block of a given length appears only once, no longer
   block starting at that position can appear twice either, because any match
   would have to match the shorter block first. So a candidate with no partner is
   dropped and never grown again. In ordinary code nearly everything is unique
   after two or three statements, so almost all candidates die in the first round.

**Result:**

```
 100 functions (  399 lines):   0.031 s   peak RSS    12.5 MB
 250 functions (  999 lines):   0.074 s   peak RSS    14.8 MB
 500 functions ( 1999 lines):   0.148 s   peak RSS    18.0 MB
1000 functions ( 3999 lines):   0.299 s   peak RSS    25.6 MB
2000 functions ( 7999 lines):   0.616 s   peak RSS    39.7 MB
```

At the 1000-line mark that is 14 times faster and 85 times less memory, and the
growth is now linear rather than cubic. An 8000-line file, which the old version
could not finish at all, now takes under a second.

**All 16 duplicate-detection tests passed unchanged**, which is what gave me
confidence the rewrite preserved the behaviour rather than just being faster. The
grouping semantics are identical; only the bookkeeping changed.

### The tool caught my own regression

The first version of the rewrite failed the self-analysis test:

```
FAIL: test_no_module_exceeds_the_default_complexity_limit (module='duplication.py')
AssertionError: 12 not less than or equal to 10

FAIL: test_every_module_is_free_of_issues (module='duplication.py')
116:CPX001 function '_windows_by_fingerprint' has a cyclomatic complexity of 12,
which is above the limit of 10
```

My new function was over the limit the tool enforces. I split it into
`_encoded_structures`, `_initial_candidates` and `_grow_candidates`, which brought
it to 5 and reads better besides. This is the second time the self-analysis test
has caught something, and the first time it caught a regression I introduced
myself within minutes of writing it.

### Traceability

I then tagged the remaining tests with the requirement IDs they cover and built a
traceability matrix in `test-design.md` covering all 17 functional requirements,
all 8 non-functional requirements, all 15 behaviours, all 12 boundary conditions
and all 9 invalid inputs. Two non-functional requirements (standard library only,
and "a new rule means a new module") are properties of the code's shape rather
than its behaviour, so I marked them as structural instead of pretending a runtime
assertion covers them.

**Final state:** 190 tests, all passing, 99% coverage.
