import logging
import sys
from enum import Enum


class LogLevel(str, Enum):
    critical = "CRITICAL"
    error = "ERROR"
    warning = "WARNING"
    info = "INFO"
    debug = "DEBUG"


log_level = LogLevel.info

# Configure the root logger
logging.basicConfig(
    level=getattr(logging, log_level.upper(), None),
    format="%(asctime)s.%(msecs)03d --%(name)s-- %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Create a logger for the package
logger = logging.getLogger(__name__)
logger.debug("Logging is configured for the package.")

# Configure the package version
if sys.version_info < (3, 8):
    from importlib_metadata import version  # noqa
else:
    from importlib.metadata import version  # noqa

__version__ = version("CATio")
del version

__all__ = ["__version__"]
