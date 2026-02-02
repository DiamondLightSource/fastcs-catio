"""Custom logging configuration for fastcs-catio.

Adds a VERBOSE logging level below DEBUG for very detailed tracing.
"""

import logging
from typing import Any

# Define VERBOSE level (between DEBUG=10 and NOTSET=0)
VERBOSE = 5
logging.addLevelName(VERBOSE, "VERBOSE")


class VerboseLogger(logging.Logger):
    """Logger subclass with verbose() method for VERBOSE level logging."""

    def verbose(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a message at VERBOSE level.

        Args:
            message: The log message format string
            *args: Arguments for message formatting
            **kwargs: Keyword arguments passed to _log
        """
        if self.isEnabledFor(VERBOSE):
            self._log(VERBOSE, message, args, **kwargs)


# Set the custom logger class as the default
logging.setLoggerClass(VerboseLogger)


def get_logger(name: str) -> VerboseLogger:
    """Get a logger with VERBOSE support.

    Args:
        name: Logger name (typically __name__)

    Returns:
        A VerboseLogger instance with verbose() method available
    """
    logger = logging.getLogger(name)
    # Cast is safe because we set the logger class above
    return logger  # type: ignore[return-value]
