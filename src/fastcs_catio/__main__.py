"""Interface for ``python -m fastcs_catio``."""

import logging
import os
import socket
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from fastcs.launch import FastCS
from fastcs.logging import LogLevel as FastCSLogLevel
from fastcs.logging import configure_logging
from fastcs.transports.epics.ca.transport import EpicsCATransport
from fastcs.transports.epics.options import (
    EpicsDocsOptions,
    EpicsGUIOptions,
    EpicsIOCOptions,
)
from softioc.imports import callbackSetQueueSize

from fastcs_catio.logging import VERBOSE  # noqa: F401 - registers VERBOSE level
from fastcs_catio.terminal_config import set_terminal_types_patterns

from . import __version__
from .catio_controller import (
    CATioServerController,
)
from .client import RemoteRoute

__all__ = ["main"]

CALLBACK_SIZE: int = 50000

app = typer.Typer(no_args_is_help=True)

callbackSetQueueSize(CALLBACK_SIZE)


class LogLevel(str, Enum):
    critical = "CRITICAL"
    error = "ERROR"
    warning = "WARNING"
    info = "INFO"
    debug = "DEBUG"
    verbose = "VERBOSE"


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
    ] = "127.0.0.1",
    target_port: Annotated[
        int,
        typer.Argument(
            help="Ams port of the the target device.",
        ),
    ] = 27905,
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
    ] = 1.0,
    notification_period: Annotated[
        float,
        typer.Option(
            help="Period in seconds at which notifications from the EtherCAT devices \
                are updated (it must be larger than the EtherCAT cycle time!).",
            rich_help_panel="Secondary Arguments",
        ),
    ] = 0.2,
    terminal_defs: Annotated[
        str | None,
        typer.Option(
            help=(
                "Glob pattern for terminal definition YAML files. "
                "Can use wildcards like '*.yaml' or '**/*.yaml' for recursive search. "
                "Defaults to DLS yaml descriptions embedded in the python package. "
                "May also be a comma separated list of glob patterns or filenames."
            ),
            rich_help_panel="Secondary Arguments",
        ),
    ] = None,
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
    'python -m fastcs_catio ioc BLxx-EA-CATIO-01 ws368'

    (use '[command] --help' for more details)
    """
    # Configure fastcs loguru logger first - map VERBOSE to DEBUG since fastcs doesn't
    # have it. This gives us colored output via loguru.
    level_name = log_level.upper()
    fastcs_level_name = "DEBUG" if level_name == "VERBOSE" else level_name
    fastcs_level = FastCSLogLevel[fastcs_level_name]
    configure_logging(level=fastcs_level)

    # Configure standard library logging to forward to loguru for colored output
    # Handle VERBOSE level which is custom to fastcs-catio
    level_value = getattr(logging, level_name, None)
    if level_value is None and level_name == "VERBOSE":
        level_value = VERBOSE
    logging.basicConfig(level=level_value, handlers=[])

    # Intercept our package's logger to forward to loguru
    from fastcs.logging import intercept_std_logger

    intercept_std_logger("fastcs_catio")

    logger = logging.getLogger(__name__)
    logger.debug("Logging is configured for the package.")

    # Set up terminal definitions path - can be comma-separated patterns
    if terminal_defs is not None:
        terminal_patterns = [p.strip() for p in terminal_defs.split(",")]

        # Configure the dynamic controller factory with terminal definition patterns
        set_terminal_types_patterns(terminal_patterns)
        logger.info(f"Using terminal definition patterns: {terminal_patterns}")

    # Define EPICS GUI screens path
    default_path = Path(os.path.join(Path.cwd(), "screens"))
    ui_path = screens_dir if screens_dir.is_dir() else default_path

    # Define EPICS ChannelAccess/PVA transport parameters
    epics_transport = EpicsCATransport(
        epicsca=EpicsIOCOptions(pv_prefix=pv_prefix),
        docs=EpicsDocsOptions(),
        gui=EpicsGUIOptions(
            output_path=ui_path / "catio.bob", title=f"CATio - {pv_prefix}"
        ),
    )

    # Get the Beckhoff TwinCAT server IP address in case the server name was provided
    ip = (
        socket.gethostbyname(tcp_server)
        if not (tcp_server.count(".") == 3)
        else tcp_server
    )

    # Specify the parameters for the remote route to the Beckhoff TwinCAT server
    route = RemoteRoute(ip)

    # Instantiate the CATio controller
    controller = CATioServerController(
        ip, route, target_port, poll_period, notification_period
    )

    # Launch the CATio IOC with FastCS
    launcher = FastCS(controller, transports=[epics_transport])
    launcher.run()


if __name__ == "__main__":
    app()

# # TO DO: make the yaml config option work if it's preferred
# # if using a yaml file config: python -m fastcs_catio run
# #     ./src/fastcs_catio/catio_controller.yaml
# if __name__ == "__main__":
#     transport = EpicsCATransport(
#        ca_ioc=EpicsIOCOptions(pv_prefix="BLxxI-EA-CATIO-01")
# )
#     route = CATioRemoteRoute(remote=ip, route_name="test_route", password="DIAMOND")
#     connection = CATioConnectionSettings(target_ip=ip, target_port=target_port)
#     timings = CATioScanTimings()
#     controller_settings = CATioControllerSettings(
#         remote_route=route, tcp_settings=connection, scan_timings=timings
#     )
#     launch(CATioServerController, version=__version__)
