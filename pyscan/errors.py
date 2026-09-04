"""Exceptions raised by PyScan.

Everything inherits from AnalyzerError so a caller who does not care which kind
of problem occurred can catch a single type.
"""


class AnalyzerError(Exception):
    """Base class for every error raised by PyScan."""


class InvalidSourceError(AnalyzerError):
    """The source argument was not a string."""


class SourceParseError(AnalyzerError):
    """The source could not be parsed as Python."""

    def __init__(self, message, line=None):
        super().__init__(message)
        self.line = line


class SourceFileError(AnalyzerError):
    """A file could not be read (missing, unreadable, or not a file)."""


class ConfigurationError(AnalyzerError):
    """The analyser was configured with values that do not make sense."""
