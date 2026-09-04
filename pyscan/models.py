"""Value objects returned by the analyser."""

from dataclasses import dataclass, field
from typing import Optional, Tuple

SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


@dataclass(frozen=True)
class Issue:
    """One problem found in the source code.

    `name` is the specific thing the issue is about (a variable name, a function
    name) so that messages can be checked in tests without matching whole
    sentences. `related_lines` is used by the duplicate-code rule to point at the
    other copies.
    """

    rule_id: str
    line: int
    message: str
    severity: str = SEVERITY_WARNING
    name: Optional[str] = None
    related_lines: Tuple[int, ...] = field(default_factory=tuple)

    @property
    def sort_key(self):
        return (self.line, self.rule_id, self.name or "")


@dataclass(frozen=True)
class Metrics:
    """Numbers describing the file as a whole.

    Every field defaults to zero so that an empty file produces a valid,
    all-zero Metrics rather than a crash or a half-filled object.
    """

    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    function_count: int = 0
    class_count: int = 0
    average_complexity: float = 0.0
    max_complexity: int = 0
    comment_ratio: float = 0.0


@dataclass(frozen=True)
class AnalysisReport:
    """Everything the analyser found in one source file."""

    issues: Tuple[Issue, ...] = field(default_factory=tuple)
    metrics: Metrics = field(default_factory=Metrics)

    def issues_for(self, rule_id):
        """Return only the issues raised by one rule, in report order."""
        return tuple(issue for issue in self.issues if issue.rule_id == rule_id)

    @property
    def has_issues(self):
        return len(self.issues) > 0
