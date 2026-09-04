"""Analyser configuration and the catalogue of rule IDs."""

from dataclasses import dataclass, field
from typing import FrozenSet

from pyscan.errors import ConfigurationError

RULE_DESCRIPTIONS = {
    "CPX001": "function cyclomatic complexity exceeds the threshold",
    "UNU001": "local variable assigned but never read",
    "UNU002": "import never used in the module",
    "DUP001": "block of statements duplicated elsewhere in the file",
    "NAM001": "function or method name is not snake_case",
    "NAM002": "variable name is not snake_case",
    "NAM003": "class name is not PascalCase",
    "NAM004": "function argument name is not snake_case",
    "NAM005": "name shadows a Python built-in",
}

ALL_RULES = frozenset(RULE_DESCRIPTIONS)

DEFAULT_MAX_COMPLEXITY = 10
DEFAULT_MIN_DUPLICATE_STATEMENTS = 4


@dataclass(frozen=True)
class AnalyzerConfig:
    """Thresholds and rule switches.

    Validation happens on construction rather than during analysis, so a bad
    configuration fails immediately instead of halfway through a run.
    """

    max_complexity: int = DEFAULT_MAX_COMPLEXITY
    min_duplicate_statements: int = DEFAULT_MIN_DUPLICATE_STATEMENTS
    disabled_rules: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self):
        if isinstance(self.max_complexity, bool) or not isinstance(self.max_complexity, int):
            raise ConfigurationError("max_complexity must be an integer")
        if self.max_complexity < 0:
            raise ConfigurationError(
                "max_complexity must be zero or greater, got %r" % (self.max_complexity,)
            )
        if (
            isinstance(self.min_duplicate_statements, bool)
            or not isinstance(self.min_duplicate_statements, int)
        ):
            raise ConfigurationError("min_duplicate_statements must be an integer")
        if self.min_duplicate_statements < 1:
            raise ConfigurationError(
                "min_duplicate_statements must be at least 1, got %r"
                % (self.min_duplicate_statements,)
            )

        # Normalise to a frozenset so the config stays hashable and immutable
        # even if the caller passed a list.
        object.__setattr__(self, "disabled_rules", frozenset(self.disabled_rules))

        unknown = sorted(self.disabled_rules - ALL_RULES)
        if unknown:
            raise ConfigurationError("unknown rule id(s): %s" % ", ".join(unknown))

    def is_enabled(self, rule_id):
        return rule_id not in self.disabled_rules
