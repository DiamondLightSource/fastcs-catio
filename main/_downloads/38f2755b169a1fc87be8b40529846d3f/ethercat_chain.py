"""
EtherCAT chain emulation for ADS simulation server.

This module provides classes to represent and emulate an EtherCAT chain
with devices and slaves, configured from a YAML description file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from catio_terminals.models import RuntimeSymbolsConfig
    from catio_terminals.models import TerminalType as ModelTerminalType
else:
    # Import TerminalType at runtime if available (rename to avoid conflict)
    try:
        from catio_terminals.models import TerminalType as ModelTerminalType
    except ImportError:
        ModelTerminalType = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Default CoE index offset for slave operational parameters
COE_OPERATIONAL_PARAMS_BASE = 0x8000


@dataclass
class SymbolDefinition:
    """Definition of a symbol from a terminal type."""

    name_template: str
    index_group: int
    size: int = 0
    ads_type: int = 33  # BIT by default
    type_name: str = "BIT"
    channels: int = 1

    def expand_symbols(
        self, device_id: int, terminal_name: str, base_offset: int
    ) -> list[dict[str, Any]]:
        """Expand this definition into actual symbols for a terminal.

        Args:
            device_id: The device ID this terminal belongs to.
            terminal_name: The name of the terminal (e.g., "Term 4 (EL2024)").
            base_offset: Base offset for index calculations.

        Returns:
            List of symbol dictionaries ready for symbol table.
        """
        symbols = []

        for ch in range(1, self.channels + 1):
            # Format the name template with dot separator (matches hardware format)
            if self.channels == 1:
                # Single channel - don't include channel number in name
                name = f"{terminal_name}.{self.name_template}"
            else:
                name = f"{terminal_name}.{self.name_template.format(channel=ch)}"

            # Calculate offset based on channel and size
            if self.size == 0:  # Bit
                offset = base_offset * 32 + (ch - 1)
            else:
                offset = base_offset * 64 + (ch - 1) * self.size

            name_formatted = self.name_template.format(channel=ch)
            symbols.append(
                {
                    "name": name,
                    "index_group": self.index_group,
                    "index_offset": offset,
                    "size": self.size,
                    "ads_type": self.ads_type,
                    "type_name": self.type_name,
                    "comment": f"{terminal_name} {name_formatted}",
                }
            )

        return symbols


@dataclass
class TerminalType:
    """Definition of a terminal type with its symbols."""

    name: str
    description: str = ""
    identity: SlaveIdentity | None = None
    symbols: list[SymbolDefinition] = field(default_factory=list)
    group_type: str | None = None


@dataclass
class SlaveIdentity:
    """CANopen identity for an EtherCAT slave."""

    vendor_id: int = 2  # Beckhoff vendor ID
    product_code: int = 0
    revision_number: int = 0
    serial_number: int = 0

    def to_bytes(self) -> bytes:
        """Convert identity to bytes (4 x uint32)."""
        return (
            self.vendor_id.to_bytes(4, "little")
            + self.product_code.to_bytes(4, "little")
            + self.revision_number.to_bytes(4, "little")
            + self.serial_number.to_bytes(4, "little")
        )

    def vendor_id_bytes(self) -> bytes:
        """Return vendor_id as bytes."""
        return self.vendor_id.to_bytes(4, "little")

    def product_code_bytes(self) -> bytes:
        """Return product_code as bytes."""
        return self.product_code.to_bytes(4, "little")

    def revision_number_bytes(self) -> bytes:
        """Return revision_number as bytes."""
        return self.revision_number.to_bytes(4, "little")

    def serial_number_bytes(self) -> bytes:
        """Return serial_number as bytes."""
        return self.serial_number.to_bytes(4, "little")


@dataclass
class EtherCATSlave:
    """Represents a single EtherCAT slave terminal."""

    type: str
    name: str
    node: int
    position: int
    identity: SlaveIdentity = field(default_factory=SlaveIdentity)
    address: int = 0
    ecat_state: int = 0x08  # Operational state
    link_status: int = 0x00  # Good link state
    crc_counters: tuple[int, int, int, int] = (0, 0, 0, 0)
    terminal_type: TerminalType | None = None  # Simplified type for basic info
    model_terminal: ModelTerminalType | None = field(
        default=None, init=False, repr=False
    )  # Full model for PDO filtering

    @property
    def coe_index(self) -> int:
        """Get the CoE index for this slave (based on position in device)."""
        return COE_OPERATIONAL_PARAMS_BASE + self.address

    def get_type_bytes(self) -> bytes:
        """Return terminal type as null-terminated string bytes."""
        return self.type.encode("cp1252") + b"\x00"

    def get_name_bytes(self) -> bytes:
        """Return terminal name as null-terminated string bytes."""
        return self.name.encode("cp1252") + b"\x00"

    def get_state_bytes(self) -> bytes:
        """Return EtherCAT state and link status as bytes."""
        return bytes([self.ecat_state, self.link_status])

    def get_crc_bytes(self) -> bytes:
        """Return CRC counters for all ports as bytes."""
        result = b""
        for crc in self.crc_counters:
            result += crc.to_bytes(4, "little")
        return result

    def get_symbols(
        self,
        device_id: int,
        runtime_symbols: RuntimeSymbolsConfig | None = None,
    ) -> list[dict[str, Any]]:
        """Get all symbols for this slave based on its terminal type.

        Args:
            device_id: The device ID this slave belongs to.
            runtime_symbols: Optional runtime symbols config to include WcState etc.

        Returns:
            List of symbol dictionaries.
        """
        if not self.terminal_type:
            return []

        symbols = []

        # Use model_terminal if available to get active symbol indices
        if self.model_terminal is not None:
            active_indices = self.model_terminal.get_active_symbol_indices()
        else:
            # Fallback: use all symbols if no model terminal available
            active_indices = set(range(len(self.terminal_type.symbols)))

        # Add symbols from terminal type definition (only active ones
        # based on PDO group)
        for idx, sym_def in enumerate(self.terminal_type.symbols):
            # Skip symbols not in the active PDO group
            if idx not in active_indices:
                continue
            symbols.extend(sym_def.expand_symbols(device_id, self.name, self.address))

        # Add runtime symbols (WcState, InputToggle, etc.) if available
        if runtime_symbols:
            terminal_id = self.type  # e.g., "EL2024"
            group_type = self.terminal_type.group_type
            runtime_sym_nodes = runtime_symbols.get_symbols_for_terminal(
                terminal_id, group_type
            )
            for sym_node in runtime_sym_nodes:
                # Convert SymbolNode to SymbolDefinition and expand
                sym_def = SymbolDefinition(
                    name_template=sym_node.name_template,
                    index_group=sym_node.index_group,
                    size=sym_node.size,
                    ads_type=sym_node.ads_type,
                    type_name=sym_node.type_name,
                    channels=sym_node.channels,
                )
                symbols.extend(
                    sym_def.expand_symbols(device_id, self.name, self.address)
                )

        return symbols


@dataclass
class EtherCATDevice:
    """Represents an EtherCAT master device."""

    id: int
    name: str
    type: int = 94  # IODEVICETYPE_ETHERCAT
    netid: str = "10.0.0.1.3.1"
    identity: SlaveIdentity = field(default_factory=SlaveIdentity)
    slaves: list[EtherCATSlave] = field(default_factory=list)

    # Frame counters
    frame_time: int = 0
    cyclic_sent: int = 0
    cyclic_lost: int = 0
    acyclic_sent: int = 0
    acyclic_lost: int = 0

    # Master state machine
    master_state: int = 0x08  # Operational

    def get_netid_bytes(self) -> bytes:
        """Convert netid string to 6 bytes."""
        parts = [int(x) for x in self.netid.split(".")]
        if len(parts) != 6:
            raise ValueError(f"Invalid netid format: {self.netid}")
        return bytes(parts)

    def get_name_bytes(self) -> bytes:
        """Return device name as null-terminated string bytes."""
        return self.name.encode("cp1252") + b"\x00"

    @property
    def slave_count(self) -> int:
        """Return number of slaves."""
        return len(self.slaves)

    def get_slave_addresses(self) -> list[int]:
        """Return list of slave addresses."""
        return [slave.address for slave in self.slaves]

    def get_slave_by_address(self, address: int) -> EtherCATSlave | None:
        """Find slave by its EtherCAT address."""
        for slave in self.slaves:
            if slave.address == address:
                return slave
        return None

    def get_slave_by_index(self, index: int) -> EtherCATSlave | None:
        """Find slave by its index in the chain."""
        if 0 <= index < len(self.slaves):
            return self.slaves[index]
        return None

    def get_frame_counters_bytes(self) -> bytes:
        """Return frame counters as bytes (5 x uint32)."""
        return (
            self.frame_time.to_bytes(4, "little")
            + self.cyclic_sent.to_bytes(4, "little")
            + self.cyclic_lost.to_bytes(4, "little")
            + self.acyclic_sent.to_bytes(4, "little")
            + self.acyclic_lost.to_bytes(4, "little")
        )

    def get_device_symbols(self) -> list[dict[str, Any]]:
        """Get device-level symbols for the EtherCAT master.

        Real hardware exposes these symbols for the EtherCAT master device:
        - Inputs: Frm0State, Frm0WcState, Frm0InputToggle, SlaveCount, DevState
        - Outputs: Frm0Ctrl, Frm0WcCtrl, DevCtrl

        Returns:
            List of device-level symbol dictionaries.
        """
        # Base offset for device symbols (from hardware observation)
        base_offset = 0x5F0
        device_name = self.name

        # Index groups: 0xF030 for inputs (process data read), 0xF020 for outputs
        index_group_input = 0xF030
        index_group_output = 0xF020

        # Note: Using ADS_TYPE_BIT (33) because the client's symbol_lookup doesn't
        # handle ADS_TYPE_UINT16 (18). Real hardware uses UINT16 for these symbols.
        # TODO: Update client symbol_lookup to handle ADS_TYPE_UINT16 properly.
        ads_type_bit = 33  # ADS_TYPE_BIT - client handles this

        symbols = [
            # Input symbols
            {
                "name": f"{device_name}.Inputs.Frm0State",
                "index_group": index_group_input,
                "index_offset": base_offset,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Input Frame status symbol for the EtherCAT Master device.",
            },
            {
                "name": f"{device_name}.Inputs.Frm0WcState",
                "index_group": index_group_input,
                "index_offset": base_offset + 2,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Input Frame working counter status symbol for the "
                "EtherCAT Master device.",
            },
            {
                "name": f"{device_name}.Inputs.Frm0InputToggle",
                "index_group": index_group_input,
                "index_offset": base_offset + 4,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Input Frame input toggle symbol for the "
                "EtherCAT Master device.",
            },
            {
                "name": f"{device_name}.Inputs.SlaveCount",
                "index_group": index_group_input,
                "index_offset": base_offset + 10,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "SlaveCount symbol for the EtherCAT Master device.",
            },
            {
                "name": f"{device_name}.Inputs.DevState",
                "index_group": index_group_input,
                "index_offset": base_offset + 14,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Device Input Status symbol for the EtherCAT Master device.",
            },
            # Output symbols
            {
                "name": f"{device_name}.Outputs.Frm0Ctrl",
                "index_group": index_group_output,
                "index_offset": base_offset,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Output Frame control symbol for the "
                "EtherCAT Master device.",
            },
            {
                "name": f"{device_name}.Outputs.Frm0WcCtrl",
                "index_group": index_group_output,
                "index_offset": base_offset + 2,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Output Frame working counter control symbol for the "
                "EtherCAT Master device.",
            },
            {
                "name": f"{device_name}.Outputs.DevCtrl",
                "index_group": index_group_output,
                "index_offset": base_offset + 4,
                "size": 1,
                "ads_type": ads_type_bit,
                "type_name": "BIT",
                "comment": "Device Output status symbol for the "
                "EtherCAT Master device.",
            },
        ]

        return symbols

    def get_all_symbols(
        self, runtime_symbols: RuntimeSymbolsConfig | None = None
    ) -> list[dict[str, Any]]:
        """Get all symbols from this device and all its slaves.

        Args:
            runtime_symbols: Optional runtime symbols config to include WcState etc.

        Returns:
            List of all symbol dictionaries.
        """
        # Start with device-level symbols
        symbols = self.get_device_symbols()

        # Add global runtime symbols (e.g., SyncUnits)
        if runtime_symbols:
            for runtime_sym in runtime_symbols.runtime_symbols:
                if runtime_sym.is_global:
                    # Expand global symbol (no channel substitution)
                    symbols.append(
                        {
                            "name": runtime_sym.name_template,
                            "index_group": runtime_sym.index_group,
                            "index_offset": 0x00002FB0,  # Fixed offset for SyncUnits
                            "size": runtime_sym.size,
                            "ads_type": runtime_sym.ads_type,
                            "type_name": runtime_sym.type_name,
                            "comment": runtime_sym.description or "",
                        }
                    )

        # Add symbols from all slaves
        for slave in self.slaves:
            symbols.extend(slave.get_symbols(self.id, runtime_symbols))
        return symbols


@dataclass
class ServerInfo:
    """I/O Server information."""

    name: str = "TwinCAT System"
    version: str = "3.1"
    build: int = 4024
    major_version: int = 3
    minor_version: int = 1

    def get_name_bytes(self) -> bytes:
        """Return server name as bytes (max 16 bytes)."""
        name_bytes = self.name.encode("cp1252")
        return name_bytes[:16].ljust(16, b"\x00")


class EtherCATChain:
    """
    Manages an EtherCAT chain with multiple devices and slaves.

    Loads configuration from YAML and provides methods to query
    device and slave information.
    """

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize the EtherCAT chain.

        Args:
            config_path: Path to YAML configuration file. If None, uses default config.
        """
        self.server_info = ServerInfo()
        self.devices: dict[int, EtherCATDevice] = {}
        self.terminal_types: dict[str, TerminalType] = {}
        self.model_terminals: dict[
            str, ModelTerminalType
        ] = {}  # Full terminal models for PDO filtering
        self.runtime_symbols: RuntimeSymbolsConfig | None = None

        # Load runtime symbols configuration
        self._load_runtime_symbols()

        # Load terminal types from separate YAML files
        self._load_terminal_types()

        if config_path:
            self.load_config(config_path)
        else:
            # Load default config from package
            default_config = Path(__file__).parent / "server_config.yaml"
            if default_config.exists():
                self.load_config(default_config)
            else:
                logger.warning("No config file found, using empty chain")

    def _load_runtime_symbols(self) -> None:
        """Load runtime symbols configuration from catio_terminals package."""
        try:
            from catio_terminals.models import RuntimeSymbolsConfig

            runtime_symbols_path = (
                Path(__file__).parents[2]
                / "src"
                / "catio_terminals"
                / "config"
                / "runtime_symbols.yaml"
            )
            if runtime_symbols_path.exists():
                self.runtime_symbols = RuntimeSymbolsConfig.from_yaml(
                    runtime_symbols_path
                )
                logger.debug(
                    f"Loaded {len(self.runtime_symbols.runtime_symbols)} "
                    "runtime symbol definitions"
                )
            else:
                logger.warning(
                    f"Runtime symbols file not found: {runtime_symbols_path}"
                )
        except ImportError:
            logger.warning("catio_terminals package not available for runtime symbols")

    def _load_terminal_types(self) -> None:
        """
        Load terminal type definitions from YAML files.

        Loads terminal types from:
        1. Built-in terminal types in src/catio_terminals/terminals/
        2. Legacy terminal_types in the main config (for backwards compatibility)
        """
        # Try to load full model TerminalType definitions for PDO group filtering
        try:
            from catio_terminals.models import TerminalConfig

            terminals_path = (
                Path(__file__).parents[2]
                / "src"
                / "catio_terminals"
                / "terminals"
                / "terminal_types.yaml"
            )
            if terminals_path.exists():
                config = TerminalConfig.from_yaml(terminals_path)
                self.model_terminals = config.terminal_types
                logger.debug(f"Loaded {len(self.model_terminals)} model terminal types")
            else:
                logger.warning(f"Terminal types file not found: {terminals_path}")
        except ImportError:
            logger.warning("catio_terminals not available, PDO filtering disabled")
            self.model_terminals = {}

        # Try to find the terminals directory relative to the package root
        # First check from the src folder
        pkg_root = Path(__file__).parents[2] / "src" / "catio_terminals" / "terminals"

        if not pkg_root.exists():
            # Fall back to checking relative to current file location
            pkg_root = Path(__file__).parent / "terminals"

        if pkg_root.exists():
            # Load all YAML files in the terminals directory
            for yaml_file in sorted(pkg_root.glob("*.yaml")):
                try:
                    with open(yaml_file) as f:
                        terminal_config = yaml.safe_load(f)

                    if "terminal_types" in terminal_config:
                        for type_name, type_config in terminal_config[
                            "terminal_types"
                        ].items():
                            self.terminal_types[type_name] = self._parse_terminal_type(
                                type_name, type_config
                            )
                        logger.debug(
                            f"Loaded {len(terminal_config['terminal_types'])} "
                            f"terminal types from {yaml_file.name}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to load terminal types from {yaml_file}: {e}"
                    )
        else:
            logger.warning(f"Terminal types directory not found: {pkg_root}")

    def load_config(self, config_path: str | Path) -> None:
        """
        Load EtherCAT chain configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        self._parse_config(config)
        logger.info(
            f"Loaded EtherCAT chain config: {len(self.devices)} device(s), "
            f"{self.total_slave_count} slave(s), "
            f"{len(self.terminal_types)} terminal type(s)"
        )

    def _parse_config(self, config: dict[str, Any]) -> None:
        """Parse configuration dictionary into chain objects."""
        # Parse server info
        if "server" in config:
            srv = config["server"]
            self.server_info = ServerInfo(
                name=srv.get("name", "TwinCAT System"),
                version=srv.get("version", "3.1"),
                build=srv.get("build", 4024),
                major_version=int(srv.get("version", "3.1").split(".")[0]),
                minor_version=int(srv.get("version", "3.1").split(".")[1]),
            )

        # Parse terminal types first
        if "terminal_types" in config:
            for type_name, type_config in config["terminal_types"].items():
                self.terminal_types[type_name] = self._parse_terminal_type(
                    type_name, type_config
                )

        # Parse devices
        if "devices" in config:
            for dev_config in config["devices"]:
                device = self._parse_device(dev_config)
                self.devices[device.id] = device

    def _parse_terminal_type(
        self, type_name: str, type_config: dict[str, Any]
    ) -> TerminalType:
        """Parse a terminal type configuration."""
        identity = None
        if "identity" in type_config:
            id_config = type_config["identity"]
            identity = SlaveIdentity(
                vendor_id=id_config.get("vendor_id", 2),
                product_code=id_config.get("product_code", 0),
                revision_number=id_config.get("revision_number", 0),
                serial_number=id_config.get("serial_number", 0),
            )

        symbols = []
        # Support both "symbols" and "symbol_nodes" keys for compatibility
        sym_configs = type_config.get("symbol_nodes", type_config.get("symbols", []))
        for sym_config in sym_configs:
            symbols.append(
                SymbolDefinition(
                    name_template=sym_config.get("name_template", ""),
                    index_group=sym_config.get("index_group", 0xF021),
                    size=sym_config.get("size", 0),
                    ads_type=sym_config.get("ads_type", 33),
                    type_name=sym_config.get("type_name", "BIT"),
                    channels=sym_config.get("channels", 1),
                )
            )

        return TerminalType(
            name=type_name,
            description=type_config.get("description", ""),
            identity=identity,
            symbols=symbols,
            group_type=type_config.get("group_type"),
        )

    def _parse_device(self, dev_config: dict[str, Any]) -> EtherCATDevice:
        """Parse a device configuration dictionary."""
        identity = SlaveIdentity()
        if "identity" in dev_config:
            id_config = dev_config["identity"]
            identity = SlaveIdentity(
                vendor_id=id_config.get("vendor_id", 2),
                product_code=id_config.get("product_code", 0),
                revision_number=id_config.get("revision_number", 0),
                serial_number=id_config.get("serial_number", 0),
            )

        device = EtherCATDevice(
            id=dev_config.get("id", 1),
            name=dev_config.get("name", "Device 1 (EtherCAT)"),
            type=dev_config.get("type", 94),
            netid=dev_config.get("netid", "10.0.0.1.3.1"),
            identity=identity,
        )

        # Parse slaves and assign addresses
        if "slaves" in dev_config:
            address = 1001  # Starting address
            for slave_config in dev_config["slaves"]:
                slave = self._parse_slave(slave_config)
                slave.address = address
                device.slaves.append(slave)
                address += 1

        return device

    def _parse_slave(self, slave_config: dict[str, Any]) -> EtherCATSlave:
        """Parse a slave configuration dictionary."""
        slave_type = slave_config.get("type", "EL2024")

        # Look up terminal type for identity and symbols
        terminal_type = self.terminal_types.get(slave_type)

        # Use identity from terminal type if not specified in slave config
        if "identity" in slave_config:
            id_config = slave_config["identity"]
            identity = SlaveIdentity(
                vendor_id=id_config.get("vendor_id", 2),
                product_code=id_config.get("product_code", 0),
                revision_number=id_config.get("revision_number", 0),
                serial_number=id_config.get("serial_number", 0),
            )
        elif terminal_type and terminal_type.identity:
            identity = terminal_type.identity
        else:
            identity = SlaveIdentity()

        slave = EtherCATSlave(
            type=slave_type,
            name=slave_config.get("name", "Unknown"),
            node=slave_config.get("node", 0),
            position=slave_config.get("position", 0),
            identity=identity,
            terminal_type=terminal_type,
        )

        # Attach model terminal if available for PDO group filtering
        if hasattr(self, "model_terminals") and slave_type in self.model_terminals:
            slave.model_terminal = self.model_terminals[slave_type]

        return slave

    @property
    def device_count(self) -> int:
        """Return number of devices."""
        return len(self.devices)

    @property
    def device_ids(self) -> list[int]:
        """Return list of device IDs."""
        return list(self.devices.keys())

    @property
    def total_slave_count(self) -> int:
        """Return total number of slaves across all devices."""
        return sum(dev.slave_count for dev in self.devices.values())

    @property
    def total_symbol_count(self) -> int:
        """
        Return total number of symbols across all devices after client-side expansion.

        The client expands certain BIGTYPE symbol nodes into multiple symbols:
        - CNT Inputs_TYPE -> 2 symbols (status + counter value)
        - CNT Outputs_TYPE -> 2 symbols (status + set counter value)
        - AI Standard Channel 1_TYPE -> 2 symbols (status + value)
        - AI Inputs Channel 1_TYPE -> 2 symbols (status + value)
        - Other types -> 1 symbol each

        Note: The client's symbol_lookup only handles certain ADS types:
        - ADS_TYPE_BIT (33)
        - ADS_TYPE_BIGTYPE (65)
        - ADS_TYPE_UINT8 (17)
        Symbols with other types (e.g., UINT16=18) are filtered out.
        """
        # ADS types that symbol_lookup handles
        handled_ads_types = {33, 65, 17}  # BIT, BIGTYPE, UINT8

        total = 0
        for dev in self.devices.values():
            for sym in dev.get_all_symbols(self.runtime_symbols):
                ads_type = sym.get("ads_type", 33)
                # Skip symbols with types that symbol_lookup doesn't handle
                if ads_type not in handled_ads_types:
                    continue

                type_name = sym["type_name"]
                # Count how many symbols this node will expand to on the client
                if type_name in ("CNT Inputs_TYPE", "CNT Outputs_TYPE"):
                    total += 2  # Expands to status + value
                elif type_name.startswith(
                    "AI Standard Channel 1_"
                ) and type_name.endswith("TYPE"):
                    total += 2  # Expands to status + value
                elif type_name.startswith(
                    "AI Inputs Channel 1_"
                ) and type_name.endswith("TYPE"):
                    total += 2  # Expands to status + value
                else:
                    total += 1  # No expansion
        return total

    def get_device(self, device_id: int) -> EtherCATDevice | None:
        """Get device by ID."""
        return self.devices.get(device_id)

    def get_device_by_netid(self, netid: str) -> EtherCATDevice | None:
        """Get device by its AMS NetID."""
        for device in self.devices.values():
            if device.netid == netid:
                return device
        return None

    def get_all_symbols(self) -> list[dict[str, Any]]:
        """Get all symbols from all devices.

        Returns:
            List of all symbol dictionaries.
        """
        symbols = []
        for device in self.devices.values():
            symbols.extend(device.get_all_symbols(self.runtime_symbols))
        return symbols

    def print_chain(self) -> None:
        """Print a visual representation of the EtherCAT chain."""
        print("\n============ Simulated EtherCAT Chain ============")
        print(f"Total symbols: {self.total_symbol_count}")
        print(f"  (Symbol nodes in YAML: {len(self.get_all_symbols())})")
        print("|")
        for device in self.devices.values():
            print(f"|----EtherCAT Master '{device.name}'")
            print("\t|")
            for slave in device.slaves:
                if slave.type in ("EK1100", "EK1110", "EK1200"):
                    if slave.type == "EK1110":
                        print(
                            f"\t|----- {slave.node}::{slave.position}\t"
                            f"-> {slave.type}\t{slave.name}"
                        )
                    else:
                        print(
                            f"\t|----- {slave.node}::{slave.position} -> {slave.name}"
                        )
                else:
                    print(
                        f"\t\t|----- {slave.node}::{slave.position}\t"
                        f"-> {slave.type}\t{slave.name}"
                    )
