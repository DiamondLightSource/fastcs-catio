"""Interface for ``python -m catio``."""

import logging
import socket
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from fastcs.launch import FastCS
from fastcs.transport.epics.ca.options import (
    EpicsCAOptions,
    EpicsDocsOptions,
    EpicsGUIOptions,
    EpicsIOCOptions,
)
from softioc.imports import callbackSetQueueSize

from . import __version__
from .catio_controller import CATioController

__all__ = ["main"]


app = typer.Typer(no_args_is_help=True)

callbackSetQueueSize(50000)


class LogLevel(str, Enum):
    critical = "CRITICAL"
    error = "ERROR"
    warning = "WARNING"
    info = "INFO"
    debug = "DEBUG"


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(  # noqa
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Print the version and exit",
    ),
):
    """Enable ADS-communication with a Beckhoff TwinCAT server."""
    pass


@app.command()
def hello():
    print("SAY HELLO")


@app.command()
def ioc(
    pv_prefix: Annotated[
        str,
        typer.Argument(
            help="Prefix PV name used for the IOC.",
            show_default="default",
        ),
    ],
    tcp_server: Annotated[
        str,
        typer.Argument(
            help="Beckhoff TwinCAT server host to connect to (name or IP address).",
        ),
    ] = "172.23.240.142",
    target_netid: Annotated[
        str,
        typer.Argument(
            help="Ams netid of the target server.",
        ),
    ] = "5.59.238.150.1.1",
    target_port: Annotated[
        int,
        typer.Argument(
            help="Ams port of the the target device.",
        ),
    ] = 27909,
    log_level: Annotated[
        LogLevel,
        typer.Option(
            help="Set the logging level.",
            case_sensitive=False,
            rich_help_panel="Secondary Arguments",
        ),
    ] = LogLevel.info,
    poll_period: Annotated[
        float,
        typer.Option(
            help="Period in seconds with which to poll the EtherCAT server.",
            rich_help_panel="Secondary Arguments",
        ),
    ] = 0.5,
    screens_dir: Annotated[
        Path,
        typer.Option(
            help="Provide a specific directory to export generated bobfiles to.",
            exists=False,
            file_okay=False,
            dir_okay=True,
            writable=True,
            readable=True,
            resolve_path=True,
            rich_help_panel="Secondary Arguments",
        ),
    ] = Path("/epics/opi"),
):
    """
    Run the EtherCAT IOC with the given PREFIX on a HOST server, e.g.
    'python -m catio ioc BLxx-EA-CATIO-01 ws368'

    (use '[command] --help' for more details)
    """
    # Configure the root logger and create a logger for the package
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="%(asctime)s.%(msecs)03d --%(name)s-- %(levelname)s: %(message)s",
        level=getattr(logging, log_level.upper(), None),
    )
    logger = logging.getLogger(__name__)
    logger.debug("Logging is configured for the package.")

    # Define EPICS GUI screens path
    ui_path = screens_dir if screens_dir.is_dir() else Path.cwd()

    # Define EPICS ChannelAccess/PVA transport parameters
    options = EpicsCAOptions(
        docs=EpicsDocsOptions(),
        gui=EpicsGUIOptions(
            output_path=ui_path / "catio.bob", title=f"CATio - {pv_prefix}"
        ),
        ca_ioc=EpicsIOCOptions(pv_prefix=pv_prefix),
    )

    # Get the Beckhoff TwinCAT server IP address in case the server name was provided
    ip = (
        socket.gethostbyname(tcp_server)
        if not (tcp_server.count(".") == 3)
        else tcp_server
    )
    # Get the Beckhoff TwinCAT server connection settings
    controller = CATioController(ip, target_netid, target_port, poll_period)
    launcher = FastCS(controller, [options])
    launcher.create_docs()
    launcher.create_gui()
    launcher.run()

    # For dvpt purpose, force the connection to terminate cleanly (after Ctrl-D).
    launcher.end()


if __name__ == "__main__":
    app()
