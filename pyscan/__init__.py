"""PyScan — a static analyser for Python source code.

The tool reads code without running it and reports complexity, unused names,
duplicated blocks, naming problems and a set of code metrics.
"""

from pyscan.analyzer import analyze_file, analyze_source
from pyscan.config import ALL_RULES, RULE_DESCRIPTIONS, AnalyzerConfig
from pyscan.errors import (
    AnalyzerError,
    ConfigurationError,
    InvalidSourceError,
    SourceFileError,
    SourceParseError,
)
from pyscan.models import AnalysisReport, Issue, Metrics

__version__ = "1.0.0"

__all__ = [
    "ALL_RULES",
    "RULE_DESCRIPTIONS",
    "AnalysisReport",
    "AnalyzerConfig",
    "AnalyzerError",
    "ConfigurationError",
    "InvalidSourceError",
    "Issue",
    "Metrics",
    "SourceFileError",
    "SourceParseError",
    "analyze_file",
    "analyze_source",
]
