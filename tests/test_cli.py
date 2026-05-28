import re
import subprocess
import sys

from typer.testing import CliRunner

from fastcs_catio import __version__
from fastcs_catio.__main__ import app


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", text)


def test_cli_version():
    cmd = [sys.executable, "-m", "fastcs_catio", "--version"]
    output = subprocess.check_output(cmd).decode().strip()
    assert __version__ in output


def test_ioc_help_shows_name_mapping_options():
    """ioc --help must list all three name-mapping options."""
    runner = CliRunner()
    result = runner.invoke(app, ["ioc", "--help"])
    assert result.exit_code == 0
    # Strip ANSI escape codes before asserting: in some CI environments (e.g.
    # GitHub Actions with FORCE_COLOR set) Rich/Typer emits colour codes that
    # split option names such as "--device-prefix" into separate escape
    # sequences, causing plain-string membership tests to fail.
    output = _strip_ansi(result.output)
    assert "--device-prefix" in output
    assert "--node-prefix" in output
    assert "--module-prefix" in output
