"""Structural duplicate code detection (DUP001).

The comparison is structural, not textual: two blocks that do the same thing
with differently named variables still count as duplicates, because that is how
copy-pasted code usually looks after someone has tidied it up. Only variable
names are normalised. Method names, attribute names, operators and literal
values are all compared as they are, so `data.append(1)` and `data.remove(1)`
are correctly treated as different code.

Blocks are found with sliding windows over each list of consecutive statements.
That creates a reporting problem: six duplicated statements with a minimum block
size of four also match at window offsets 1 and 2. Two rules deal with it —
longest blocks are claimed first, and any statement already reported as part of
a duplicate cannot be reported again.
"""

import ast
import hashlib
from collections import defaultdict
from dataclasses import dataclass

from pyscan.models import Issue

# Blocks are grouped by a 128-bit digest of their structure rather than by the
# structure text itself. Keeping the full text of every candidate block was the
# original approach and it used gigabytes on a thousand-line file, because the
# same statements get stored again in every block that contains them.
DIGEST_SIZE = 16
STATEMENT_SEPARATOR = b"\x00"

IGNORED_FIELDS = frozenset({"ctx"})

# Fields holding a variable name, which is exactly what we want to ignore.
NORMALISED_FIELDS = frozenset({(ast.Name, "id"), (ast.arg, "arg")})


@dataclass(frozen=True)
class _Window:
    sequence_id: int
    start: int
    size: int
    line: int

    @property
    def positions(self):
        return {(self.sequence_id, self.start + offset) for offset in range(self.size)}


def check(context):
    min_size = context.config.min_duplicate_statements
    groups = _duplicate_groups(context.tree, min_size)

    issues = []
    for windows in groups:
        first = windows[0]
        others = tuple(window.line for window in windows[1:])
        issues.append(
            Issue(
                rule_id="DUP001",
                line=first.line,
                related_lines=others,
                message=(
                    "block of %d statements is duplicated %d times "
                    "(also at line%s %s)"
                    % (
                        first.size,
                        len(windows),
                        "" if len(others) == 1 else "s",
                        ", ".join(str(line) for line in others),
                    )
                ),
            )
        )
    return issues


def _duplicate_groups(tree, min_size):
    """Return groups of two or more matching, non-overlapping statement blocks."""
    by_fingerprint = _windows_by_fingerprint(tree, min_size)

    # Longest blocks first, so a real six-statement duplicate is claimed whole
    # instead of being carved up into four-statement pieces.
    candidates = [
        (fingerprint, windows)
        for fingerprint, windows in by_fingerprint.items()
        if len(windows) >= 2
    ]
    candidates.sort(key=lambda item: (-item[1][0].size, item[1][0].line, item[0]))

    claimed = set()
    groups = []
    for _, windows in candidates:
        chosen = _claim(windows, claimed)
        if len(chosen) >= 2:
            groups.append(chosen)
            for window in chosen:
                claimed |= window.positions

    groups.sort(key=lambda windows: windows[0].line)
    return groups


def _claim(windows, claimed):
    """Pick the occurrences that do not overlap each other or anything claimed."""
    chosen = []
    taken = set(claimed)
    for window in windows:
        positions = window.positions
        if positions & taken:
            continue
        chosen.append(window)
        taken |= positions
    return chosen


def _windows_by_fingerprint(tree, min_size):
    """Group matching blocks, growing every candidate one statement at a time.

    The key idea is that a block which is already unique can never become a
    duplicate by getting longer, so as soon as a candidate has no partner it is
    dropped and never grown again. In ordinary code almost everything is unique
    after two or three statements, so very few candidates survive past the first
    couple of rounds.

    The obvious alternative — build every block of every length up front and
    compare them — is what this replaced. It re-stored the same statements once
    for every block containing them, which is cubic in the length of the file.
    """
    sequences = _statement_sequences(tree)
    structures = _encoded_structures(sequences)
    live = _initial_candidates(structures)

    by_fingerprint = {}
    size = 0
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

    return by_fingerprint


def _encoded_structures(sequences):
    return [
        [_structure(statement).encode("utf-8") for statement in statements]
        for statements in sequences
    ]


def _initial_candidates(structures):
    """One empty running hash per possible block start."""
    return {
        (sequence_id, start): hashlib.blake2b(digest_size=DIGEST_SIZE)
        for sequence_id, encoded in enumerate(structures)
        for start in range(len(encoded))
    }


def _grow_candidates(live, structures, size):
    """Extend every surviving block by one statement and bucket them by hash."""
    buckets = defaultdict(list)
    for position, running in live.items():
        sequence_id, start = position
        index = start + size - 1
        if index >= len(structures[sequence_id]):
            continue  # this block has run off the end of its sequence
        running.update(structures[sequence_id][index])
        running.update(STATEMENT_SEPARATOR)
        buckets[running.digest()].append((position, running))
    return buckets


def _record(by_fingerprint, fingerprint, size, entries, sequences):
    """Store a group of matching blocks, if two of them can actually coexist."""
    windows = sorted(
        (
            _Window(
                sequence_id=sequence_id,
                start=start,
                size=size,
                line=sequences[sequence_id][start].lineno,
            )
            for (sequence_id, start), _ in entries
        ),
        key=lambda window: (window.line, window.sequence_id, window.start),
    )
    if len(_claim(windows, set())) >= 2:
        by_fingerprint[(fingerprint, size)] = windows


def _statement_sequences(tree):
    """Every list of consecutive statements in the file (bodies, else, finally)."""
    sequences = []
    for node in ast.walk(tree):
        for _, value in ast.iter_fields(node):
            if isinstance(value, list) and value and all(
                isinstance(item, ast.stmt) for item in value
            ):
                sequences.append(value)
    return sequences


def _structure(node):
    """A string describing a node's shape, with variable names blanked out."""
    if isinstance(node, list):
        return "[" + ",".join(_structure(item) for item in node) + "]"
    if not isinstance(node, ast.AST):
        return repr(node)

    parts = []
    for field, value in ast.iter_fields(node):
        if field in IGNORED_FIELDS:
            continue
        if (type(node), field) in NORMALISED_FIELDS:
            parts.append(field + "=*")
            continue
        parts.append(field + "=" + _structure(value))
    return "%s(%s)" % (type(node).__name__, ",".join(parts))
