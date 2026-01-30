"""XML parsing utilities for Beckhoff terminal files.

This package provides XML parsing functionality for Beckhoff EtherCAT terminals:

- constants: Regex patterns, type mappings, utility functions
- catalog: Terminal catalog parsing
- pdo: PDO (Process Data Object) parsing
- pdo_groups: AlternativeSmMapping parsing for dynamic PDO configurations
- coe: CoE (CANopen over EtherCAT) object parsing
- cache: XML file caching utilities
"""

from catio_terminals.xml.catalog import parse_terminal_catalog
from catio_terminals.xml.constants import (
    generate_terminal_url,
    get_ads_type,
    parse_hex_value,
)
from catio_terminals.xml.parser import create_default_terminal, parse_terminal_details

__all__ = [
    "parse_terminal_details",
    "create_default_terminal",
    "parse_terminal_catalog",
    "generate_terminal_url",
    "get_ads_type",
    "parse_hex_value",
]
