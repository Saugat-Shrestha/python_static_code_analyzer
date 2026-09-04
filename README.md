# PyScan — a static code analyser for Python

PRT582 Software Engineering: Process and Tools — Software Unit Testing assignment.

PyScan reads Python source code and reports on it without ever running it. It
checks cyclomatic complexity, unused variables and imports, duplicated blocks of
code and naming conventions, and it produces a set of code metrics for the file.

It was built with an AI-assisted test-driven development workflow. The tests came
first for every feature, and the whole process is written up in
[`docs/ai-development-log.md`](docs/ai-development-log.md).

## Requirements

Python 3.9 or newer. The analyser uses only the standard library. `coverage` is
needed if you want to measure test coverage, but not to run the tool.

## Installing

```bash
git clone https://github.com/Saugat-Shrestha/python_static_code_analyzer.git
cd python_static_code_analyzer

python3 -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Using it

```bash
python -m pyscan path/to/file.py
python -m pyscan pyscan/*.py
```

Options:

| Option | What it does |
|---|---|
| `--max-complexity N` | Highest cyclomatic complexity a function may have (default 10) |
| `--min-duplicate-statements N` | Smallest block counted as duplication (default 4) |
| `--disable RULE` | Turn a rule off; repeat the flag for more than one |
| `--quiet` | Print issues only, without the metrics line |
| `--list-rules` | Print every rule id with a description |

Exit codes are part of the interface so the tool can be dropped into a build:

| Code | Meaning |
|---|---|
| 0 | Nothing to report |
| 1 | Analysis succeeded and problems were found |
| 2 | The tool could not do its job (missing file, bad option, unparsable source) |

Example:

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
```

## Using it from Python

```python
from pyscan import AnalyzerConfig, analyze_source

report = analyze_source(source_code, AnalyzerConfig(max_complexity=8))

for issue in report.issues:
    print(issue.line, issue.rule_id, issue.message)

print(report.metrics.average_complexity)
```

Anything that goes wrong raises a subclass of `AnalyzerError`, so a caller who
does not need the detail can catch just that one type.

## Rules

| Rule | Meaning |
|---|---|
| `CPX001` | Function cyclomatic complexity exceeds the threshold |
| `UNU001` | Local variable assigned but never read |
| `UNU002` | Import never used in the module |
| `DUP001` | Block of statements duplicated elsewhere in the file |
| `NAM001` | Function or method name is not `snake_case` |
| `NAM002` | Variable name is not `snake_case` |
| `NAM003` | Class name is not `PascalCase` |
| `NAM004` | Function argument name is not `snake_case` |
| `NAM005` | Name shadows a Python built-in |

## Running the tests

```bash
python -m unittest discover -s tests -t .
```

With coverage:

```bash
coverage run --branch --source=pyscan -m unittest discover -s tests -t .
coverage report -m
coverage html          # writes htmlcov/index.html
```

190 tests, 99% branch coverage. The only file not covered is `__main__.py`,
which is a four-line entry point that only runs inside a subprocess where
coverage is not watching; two subprocess tests check it separately.

`tests/test_self_analysis.py` runs PyScan over its own source and fails if it
reports a single issue, so the analyser is held to the same standard it enforces
on everyone else.

## Layout

```
pyscan/
  __init__.py       public interface
  __main__.py       makes `python -m pyscan` work
  analyzer.py       parses the source and runs every checker
  astutils.py       AST helpers shared between checkers
  cli.py            command-line interface
  complexity.py     CPX001
  config.py         thresholds, rule catalogue, validation
  duplication.py    DUP001
  errors.py         exception hierarchy
  metrics.py        line counts and summary numbers
  models.py         Issue, Metrics, AnalysisReport
  naming.py         NAM001-NAM005
  unused.py         UNU001, UNU002
tests/              one module per checker, plus API, CLI and self-analysis
docs/
  specification.md        requirements, written before any code
  test-design.md          test groups and why each exists
  ai-development-log.md   the AI-TDD session as it happened
```

## Known limitations

- One file at a time. A function that is unused across the whole project still
  looks used if anything in its own file calls it.
- Static analysis cannot see anything decided at runtime. A variable read through
  `globals()["x"]` or `eval` will look unused.
- Duplicate detection normalises variable names but not literal values, so two
  blocks that differ only in a constant are not reported as duplicates.
