"""
ADS Simulation Server for testing CATio client connections.

This package provides a standalone ADS (Automation Device Specification) server
that simulates a Beckhoff TwinCAT device with an EtherCAT chain, enabling testing
without real hardware.

Usage:
    python -m tests.ads_sim [--host HOST] [--port PORT] [--config CONFIG]

Example:
    python -m tests.ads_sim --host 127.0.0.1 --port 48898 --config
        server_config_CX7000_cs2.yaml
"""

from .ethercat_chain import EtherCATChain, EtherCATSlave
from .server import ADSSimServer

__all__ = ["ADSSimServer", "EtherCATChain", "EtherCATSlave"]
