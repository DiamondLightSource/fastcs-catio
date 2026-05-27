import subprocess
import sys

from typer.testing import CliRunner

from fastcs_catio import __version__
from fastcs_catio.__main__ import app


def test_cli_version():
    cmd = [sys.executable, "-m", "fastcs_catio", "--version"]
    output = subprocess.check_output(cmd).decode().strip()
    assert __version__ in output


def test_ioc_help_shows_name_mapping_options():
    """ioc --help must list all three name-mapping options."""
    runner = CliRunner()
    result = runner.invoke(app, ["ioc", "--help"])
    assert result.exit_code == 0
    assert "--device-prefix" in result.output
    assert "--node-prefix" in result.output
    assert "--module-prefix" in result.output
