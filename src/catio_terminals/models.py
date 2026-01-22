"""Data models for terminal description YAML files."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator

from catio_terminals.ads_types import get_type_info


class Identity(BaseModel):
    """Terminal identity information."""

    vendor_id: int = Field(description="Vendor ID")
    product_code: int = Field(description="Product code")
    revision_number: int = Field(description="Revision number")


class CoESubIndex(BaseModel):
    """CANopen over EtherCAT (CoE) subindex definition."""

    subindex: int = Field(description="SubIndex number")
    name: str = Field(description="SubIndex name")
    type_name: str | None = Field(default=None, description="Data type name")
    bit_size: int | None = Field(default=None, description="Size in bits")
    access: str | None = Field(default=None, description="Access type (ro, rw, wo)")
    default_data: str | None = Field(default=None, description="Default data value")


class CoEObject(BaseModel):
    """CANopen over EtherCAT (CoE) object definition."""

    index: int = Field(description="CoE index")
    name: str = Field(description="Object name")
    type_name: str = Field(description="Data type name")
    bit_size: int = Field(description="Size in bits")
    access: str = Field(description="Access type (ro, rw, wo)")
    subindices: list[CoESubIndex] = Field(
        default_factory=list, description="List of subindices"
    )
    selected: bool = Field(
        default=False, description="Whether to include in YAML output"
    )


class SymbolNode(BaseModel):
    """Symbol node definition.

    The size and ads_type are computed from type_name using the
    ADS type mappings in ads_types.py.
    """

    name_template: str = Field(
        description="Name template with optional {channel} placeholder"
    )
    index_group: int = Field(description="ADS index group")
    type_name: str = Field(description="Type name (e.g., INT, BOOL, UINT)")
    channels: int = Field(default=1, description="Number of channels")
    access: str | None = Field(default=None, description="Read-only or Read/Write")
    fastcs_name: str | None = Field(
        default=None, description="PascalCase name for FastCS"
    )
    selected: bool = Field(
        default=True, description="Whether to include in YAML output"
    )

    # Internal storage for values loaded from YAML (not serialized)
    _size_from_yaml: int | None = None
    _ads_type_from_yaml: int | None = None

    @model_validator(mode="before")
    @classmethod
    def capture_legacy_fields(cls, data: Any) -> Any:
        """Capture size/ads_type from YAML for backwards compatibility."""
        if isinstance(data, dict):
            # Store legacy values if present, then remove them
            if "size" in data:
                data["_size_from_yaml"] = data.pop("size")
            if "ads_type" in data:
                data["_ads_type_from_yaml"] = data.pop("ads_type")
        return data

    @computed_field
    @property
    def size(self) -> int:
        """Get the data size in bytes (0 for bit types)."""
        try:
            return get_type_info(self.type_name)[1]
        except KeyError:
            # Fallback for unknown types
            return 1

    @computed_field
    @property
    def ads_type(self) -> int:
        """Get the ADS data type ID."""
        try:
            return int(get_type_info(self.type_name)[0])
        except KeyError:
            # Fallback for unknown types (BIGTYPE)
            return 65


class RuntimeSymbol(BaseModel):
    """ADS runtime symbol definition with terminal filtering.

    Runtime symbols are added dynamically by the TwinCAT/EtherCAT runtime
    and are not defined in Beckhoff's ESI XML files.

    The size and ads_type are computed from type_name using the
    ADS type mappings in ads_types.py.
    """

    name_template: str = Field(
        description="Name template with optional {channel} placeholder"
    )
    index_group: int = Field(description="ADS index group")
    type_name: str = Field(description="Type name (e.g., BIT, UINT)")
    channels: int = Field(default=1, description="Number of channels")
    access: str | None = Field(default=None, description="Read-only or Read/Write")
    fastcs_name: str | None = Field(
        default=None, description="PascalCase name for FastCS"
    )
    description: str | None = Field(default=None, description="Symbol description")
    whitelist: list[str] = Field(
        default_factory=list,
        description="Only apply to these terminal IDs (if specified)",
    )
    blacklist: list[str] = Field(
        default_factory=list,
        description="Exclude from these terminal IDs (if specified)",
    )
    group_whitelist: list[str] = Field(
        default_factory=list,
        description="Only apply to terminals in these groups (e.g., AnaIn, DigOut)",
    )
    group_blacklist: list[str] = Field(
        default_factory=list,
        description="Exclude terminals in these groups (e.g., Coupler)",
    )

    # Internal storage for values loaded from YAML (not serialized)
    _size_from_yaml: int | None = None
    _ads_type_from_yaml: int | None = None

    @model_validator(mode="before")
    @classmethod
    def capture_legacy_fields(cls, data: Any) -> Any:
        """Capture size/ads_type from YAML for backwards compatibility."""
        if isinstance(data, dict):
            if "size" in data:
                data["_size_from_yaml"] = data.pop("size")
            if "ads_type" in data:
                data["_ads_type_from_yaml"] = data.pop("ads_type")
        return data

    @computed_field
    @property
    def size(self) -> int:
        """Get the data size in bytes (0 for bit types)."""
        try:
            return get_type_info(self.type_name)[1]
        except KeyError:
            return 1

    @computed_field
    @property
    def ads_type(self) -> int:
        """Get the ADS data type ID."""
        try:
            return int(get_type_info(self.type_name)[0])
        except KeyError:
            return 65

    def applies_to_terminal(self, terminal_id: str, group_type: str | None) -> bool:
        """Check if this runtime symbol applies to a given terminal.

        Args:
            terminal_id: Terminal ID (e.g., "EL3004")
            group_type: Terminal group type (e.g., "AnaIn", "Coupler")

        Returns:
            True if the symbol should be applied to this terminal
        """
        # Check terminal ID whitelist first (most specific)
        if self.whitelist:
            return terminal_id in self.whitelist

        # Check terminal ID blacklist
        if terminal_id in self.blacklist:
            return False

        # Check group whitelist
        if self.group_whitelist:
            return group_type in self.group_whitelist if group_type else False

        # Check group blacklist
        if group_type and group_type in self.group_blacklist:
            return False

        # Default: apply to all terminals
        return True

    def to_symbol_node(self) -> SymbolNode:
        """Convert to a SymbolNode for use in terminal definitions.

        Returns:
            SymbolNode instance with the same symbol properties
        """
        return SymbolNode(
            name_template=self.name_template,
            index_group=self.index_group,
            type_name=self.type_name,
            channels=self.channels,
            access=self.access,
            fastcs_name=self.fastcs_name,
            selected=True,
        )


class RuntimeSymbolsConfig(BaseModel):
    """Configuration for ADS runtime symbols."""

    runtime_symbols: list[RuntimeSymbol] = Field(
        default_factory=list, description="List of runtime symbol definitions"
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "RuntimeSymbolsConfig":
        """Load runtime symbols configuration from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            RuntimeSymbolsConfig instance
        """
        import yaml

        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def get_symbols_for_terminal(
        self, terminal_id: str, group_type: str | None
    ) -> list[SymbolNode]:
        """Get runtime symbols applicable to a terminal.

        Args:
            terminal_id: Terminal ID (e.g., "EL3004")
            group_type: Terminal group type (e.g., "AnaIn")

        Returns:
            List of SymbolNode instances for applicable runtime symbols
        """
        return [
            sym.to_symbol_node()
            for sym in self.runtime_symbols
            if sym.applies_to_terminal(terminal_id, group_type)
        ]


class TerminalType(BaseModel):
    """Terminal type definition."""

    description: str = Field(description="Terminal description")
    identity: Identity = Field(description="Terminal identity")
    symbol_nodes: list[SymbolNode] = Field(
        default_factory=list, description="List of symbol nodes"
    )
    primitive_symbol_nodes: list[SymbolNode] = Field(
        default_factory=list,
        description="Original primitive symbols (before composite conversion)",
        exclude=True,
    )
    coe_objects: list[CoEObject] = Field(
        default_factory=list, description="CoE object dictionary"
    )
    group_type: str | None = Field(default=None, description="Terminal group type")


class TerminalConfig(BaseModel):
    """Root configuration for terminal types."""

    terminal_types: dict[str, TerminalType] = Field(
        default_factory=dict, description="Dictionary of terminal types by ID"
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "TerminalConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            TerminalConfig instance
        """
        import yaml

        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save YAML file
        """

        from ruamel.yaml import YAML

        # Fields to exclude from symbol_nodes (computed or internal)
        symbol_exclude_fields = {"selected", "size", "ads_type"}

        # Convert to dict, excluding 'selected' field and filtering items
        data = self.model_dump(exclude_none=True)

        # Filter symbol_nodes and coe_objects based on 'selected' field
        for _terminal_id, terminal_data in data.get("terminal_types", {}).items():
            if "symbol_nodes" in terminal_data:
                terminal_data["symbol_nodes"] = [
                    {k: v for k, v in sym.items() if k not in symbol_exclude_fields}
                    for sym in terminal_data["symbol_nodes"]
                    if sym.get("selected", True)
                ]
            if "coe_objects" in terminal_data:
                terminal_data["coe_objects"] = [
                    {k: v for k, v in coe.items() if k != "selected"}
                    for coe in terminal_data["coe_objects"]
                    if coe.get("selected", False)
                ]

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.preserve_quotes = True
        yaml.width = 80
        # mapping=2: indent mappings by 2 spaces
        # sequence=4: indent the dash by 2 spaces from parent (4 total from root)
        # offset=2: indent content 2 spaces from the dash
        yaml.indent(mapping=2, sequence=4, offset=2)

        with path.open("w") as f:
            # Write header comment
            f.write("# Terminal Configuration\n")
            f.write("# " + "=" * 56 + "\n")
            f.write("# Automatically generated by catio_terminals\n\n")

            # Write YAML with RedHat YAML extension formatting standards
            yaml.dump(data, f)

    def add_terminal(self, terminal_id: str, terminal: TerminalType) -> None:
        """Add a new terminal type.

        Args:
            terminal_id: Terminal identifier (e.g., "EL4004")
            terminal: TerminalType instance
        """
        self.terminal_types[terminal_id] = terminal

    def remove_terminal(self, terminal_id: str) -> None:
        """Remove a terminal type.

        Args:
            terminal_id: Terminal identifier to remove
        """
        if terminal_id in self.terminal_types:
            del self.terminal_types[terminal_id]


# ============================================================
# Composite Type Models
# ============================================================


class CompositeTypeMember(BaseModel):
    """A member field within a composite type.

    Composite types (BIGTYPE, ads_type=65) contain multiple primitive
    fields that map to individual FastCS attributes.
    """

    name: str = Field(description="Member name (e.g., 'Status', 'Value')")
    offset: int = Field(description="Byte offset within the composite type")
    type_name: str = Field(description="Primitive type (e.g., UINT, INT, DINT)")
    size: int = Field(description="Size in bytes")
    fastcs_attr: str = Field(description="FastCS attribute name")
    access: str = Field(default="read-only", description="Access type")
    description: str | None = Field(default=None, description="Member description")
    array_size: int | None = Field(default=None, description="Array size if array")


class CompositeType(BaseModel):
    """A composite type definition (TwinCAT BIGTYPE structure).

    These are structured types that contain multiple primitive members.
    They are referenced by type_name in terminal YAML files.
    """

    description: str = Field(description="Type description")
    ads_type: int = Field(default=65, description="ADS data type ID (65 = BIGTYPE)")
    size: int = Field(description="Total size in bytes")
    members: list[CompositeTypeMember] = Field(
        default_factory=list, description="List of member fields"
    )
    array_size: int | None = Field(
        default=None, description="Array size if this is an array type"
    )


class CompositeSymbolMapping(BaseModel):
    """Mapping between a composite type and the terminal group types it applies to.

    Defines which composite type to use when grouping primitive symbols from XML
    into composite symbols that TwinCAT would generate at runtime.
    """

    type_name: str = Field(
        description="The composite type name (e.g., 'AI Standard Channel 1_TYPE')"
    )
    name_template: str = Field(
        description="Symbol name template (e.g., 'AI Standard Channel {channel}')"
    )
    group_types: list[str] = Field(
        description="Terminal group types this mapping applies to (e.g., ['AnaIn'])"
    )
    member_patterns: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Patterns to match primitive symbols to composite members",
    )


class CompositeTypesConfig(BaseModel):
    """Configuration for composite type definitions."""

    composite_types: dict[str, CompositeType] = Field(
        default_factory=dict, description="Dictionary of composite types by type name"
    )
    composite_mappings: list[CompositeSymbolMapping] = Field(
        default_factory=list,
        description="Mappings from composite types to terminal groups",
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "CompositeTypesConfig":
        """Load composite types configuration from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            CompositeTypesConfig instance
        """
        import yaml

        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def get_type(self, type_name: str) -> CompositeType | None:
        """Get a composite type by name.

        Args:
            type_name: The TwinCAT type name (e.g., "AI Standard Channel 1_TYPE")

        Returns:
            CompositeType if found, None otherwise
        """
        return self.composite_types.get(type_name)

    def is_composite(self, type_name: str) -> bool:
        """Check if a type name is a composite type.

        Args:
            type_name: The type name to check

        Returns:
            True if the type is defined in composite_types
        """
        return type_name in self.composite_types

    def get_mappings(self) -> list[CompositeSymbolMapping]:
        """Get all composite symbol mappings.

        Returns:
            List of CompositeSymbolMapping instances
        """
        return self.composite_mappings

    @classmethod
    def get_default(cls) -> "CompositeTypesConfig":
        """Load the default composite types from the package.

        Returns:
            CompositeTypesConfig instance with default types
        """
        default_path = Path(__file__).parent / "config" / "composite_types.yaml"
        if default_path.exists():
            return cls.from_yaml(default_path)
        return cls()
