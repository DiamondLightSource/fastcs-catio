import subprocess
import sys

from fastcs_catio import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "fastcs_catio", "--version"]
    output = subprocess.check_output(cmd).decode().strip()
    assert __version__ in output
