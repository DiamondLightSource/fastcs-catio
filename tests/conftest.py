"""
Provides two pytest fixtures for the mock ADS server infrastructure:
- `mock_ads_server` - Async fixture that starts and stops the server automatically
- `mock_server_address` - Fixture that returns the server address for tests
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from mock_server import MockADSServer

# Prevent pytest from catching exceptions when debugging in vscode so that break on
# exception works correctly (see: https://github.com/pytest-dev/pytest/issues/7409)
if os.getenv("PYTEST_RAISE", "0") == "1":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[Any]):
        if call.excinfo is not None:
            raise call.excinfo.value
        else:
            raise RuntimeError(
                f"{call} has no exception data, an unknown error has occurred"
            )

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[Any]):
        raise excinfo.value


@pytest.fixture
async def mock_ads_server() -> AsyncGenerator[MockADSServer]:
    """Fixture that provides a running mock ADS server for testing."""
    server = MockADSServer(host="127.0.0.1", port=48898)
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
def mock_server_address() -> tuple[str, int]:
    """Fixture that provides the mock server address."""
    return ("127.0.0.1", 48898)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom pytest command-line options."""
    parser.addoption(
        "--external-simulator",
        action="store_true",
        default=False,
        help="Use an externally launched simulator instead of launching one",
    )


################################################################################
# The remaining fixtures are for the new YAML based approach ###################
################################################################################


@pytest.fixture(scope="session")
async def beckhoff_xml_cache() -> list[Any]:
    """Session-scoped fixture that downloads and parses Beckhoff XML files.

    This fixture runs once per test session and ensures the XML cache is
    populated with terminal definitions for use by other tests. If the cache
    already exists, it skips downloading/parsing and returns cached data.

    Returns:
        List of BeckhoffTerminalInfo objects parsed from XML files
    """
    from catio_terminals.beckhoff import BeckhoffClient

    client = BeckhoffClient()
    try:
        # Check if cache already exists
        cached = client.get_cached_terminals()
        if cached:
            return cached

        # Download and parse all XML files into the cache
        terminals = await client.fetch_and_parse_xml()
        return terminals
    finally:
        client.close()
