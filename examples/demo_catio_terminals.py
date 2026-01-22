#!/usr/bin/env python3
"""Demo script showing programmatic usage of catio_terminals models."""

from pathlib import Path
from tempfile import TemporaryDirectory

from catio_terminals.models import Identity, SymbolNode, TerminalConfig, TerminalType


def create_sample_config() -> TerminalConfig:
    """Create a sample terminal configuration."""
    config = TerminalConfig()

    # Add EL4004: 4-channel Analog Output 0..10V 12-bit
    config.add_terminal(
        "EL4004",
        TerminalType(
            description="4-channel Analog Output 0..10V 12-bit",
            identity=Identity(
                vendor_id=2,
                product_code=0x0FA43052,
                revision_number=0x00100000,
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="AO Output Channel {channel}",
                    index_group=0xF030,
                    size=2,
                    ads_type=65,
                    type_name="AO Output Channel 1_TYPE",
                    channels=4,
                ),
                SymbolNode(
                    name_template="WcState^WcState",
                    index_group=0xF021,
                    size=0,
                    ads_type=33,
                    type_name="BIT",
                    channels=1,
                ),
            ],
        ),
    )

    # Add EL2008: 8-channel Digital Output 24V DC
    config.add_terminal(
        "EL2008",
        TerminalType(
            description="8-channel Digital Output 24V DC, 0.5A",
            identity=Identity(
                vendor_id=2,
                product_code=0x07D83052,
                revision_number=0x00100000,
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="DO Output Channel {channel}",
                    index_group=0xF030,
                    size=1,
                    ads_type=33,
                    type_name="BIT",
                    channels=8,
                ),
                SymbolNode(
                    name_template="WcState^WcState",
                    index_group=0xF021,
                    size=0,
                    ads_type=33,
                    type_name="BIT",
                    channels=1,
                ),
            ],
        ),
    )

    return config


def main() -> None:
    """Demonstrate programmatic usage."""
    print("Creating sample terminal configuration...")
    config = create_sample_config()

    print(f"Created configuration with {len(config.terminal_types)} terminals:")
    for terminal_id, terminal in config.terminal_types.items():
        print(f"  - {terminal_id}: {terminal.description}")
        print(f"    Symbols: {len(terminal.symbol_nodes)}")

    # Save to temporary file
    with TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "demo_terminals.yaml"
        print(f"\nSaving to {yaml_path}...")
        config.to_yaml(yaml_path)

        # Read it back
        print("Reading back from YAML...")
        loaded_config = TerminalConfig.from_yaml(yaml_path)

        print(f"Loaded {len(loaded_config.terminal_types)} terminals:")
        for terminal_id, terminal in loaded_config.terminal_types.items():
            print(f"  - {terminal_id}: {terminal.description}")

        # Show YAML content
        print("\nGenerated YAML content:")
        print("-" * 60)
        print(yaml_path.read_text())
        print("-" * 60)

    print("\nDemo complete! To use the GUI, run:")
    print("  catio-terminals")


if __name__ == "__main__":
    main()
