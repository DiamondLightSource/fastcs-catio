"""Entry point for catio_terminals application."""

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer

from catio_terminals.xml_cache import XmlCache

app = typer.Typer(
    name="catio-terminals",
    help="CATio Terminal Editor - YAML terminal configuration editor",
    no_args_is_help=True,
)


@app.command()
def edit(
    file: Annotated[
        Path | None,
        typer.Argument(
            help="YAML file to open (if not provided, a file selector dialog is shown)"
        ),
    ] = None,
) -> None:
    """Launch the GUI terminal editor."""
    from catio_terminals.ui_app import run

    run(file_path=file)


@app.command(name="update-cache")
def update_cache() -> None:
    """Update the terminal database cache from Beckhoff server."""
    from catio_terminals.xml_parser import parse_terminal_catalog

    print("Updating terminal database from Beckhoff server...")
    cache = XmlCache()

    try:
        # Download and extract XML files
        success = cache.download_and_extract()
        if not success:
            print("Failed to download and extract XML files", file=sys.stderr)
            raise typer.Exit(code=1)

        print(f"XML files downloaded and extracted to {cache.xml_dir}")

        # Get XML files
        xml_files = cache.get_xml_files()
        print(f"Found {len(xml_files)} XML files")

        # Parse terminals from XML files
        print("Parsing terminal catalog...")

        def progress_callback(message: str, progress: float) -> None:
            """Display progress updates."""
            print(f"  [{progress * 100:5.1f}%] {message}")

        terminals = parse_terminal_catalog(
            xml_files,
            progress_callback=progress_callback,
        )

        print(f"Parsed {len(terminals)} terminals")

        # Save to cache
        cache.save_terminals(terminals)
        print(f"Saved terminal database to {cache.terminals_file}")

    except typer.Exit:
        raise
    except Exception as e:
        print(f"Error updating cache: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from e
    finally:
        cache.close()


@app.command(name="clean-yaml")
def clean_yaml(
    file: Annotated[
        Path | None,
        typer.Argument(help="YAML file to clean up"),
    ] = None,
    all_files: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Process all YAML files in the terminals directory",
        ),
    ] = False,
) -> None:
    """Clean up terminal YAML files by syncing with Beckhoff XML.

    This command loads YAML files, merges with XML data (dropping non-XML symbols),
    selects all symbols, and saves the cleaned file.
    """
    asyncio.run(_clean_yaml_async(file, all_files))


async def _clean_yaml_async(file: Path | None, all_files: bool) -> None:
    """Async implementation of clean-yaml command."""
    from catio_terminals.beckhoff import BeckhoffClient
    from catio_terminals.models import CompositeTypesConfig
    from catio_terminals.service_file import FileService

    # Initialize Beckhoff client
    beckhoff_client = BeckhoffClient()

    # Load composite types configuration for grouping primitives
    composite_types = CompositeTypesConfig.get_default()

    # Ensure XML cache is available
    if not beckhoff_client.get_cached_terminals():
        print(
            "No terminal cache found. Run 'catio-terminals update-cache' first.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    if all_files:
        # Process all YAML files in the terminals directory
        terminals_dir = Path(__file__).parent / "terminals"
        files_to_process = list(terminals_dir.glob("*.yaml"))

        if not files_to_process:
            print(f"No YAML files found in {terminals_dir}", file=sys.stderr)
            raise typer.Exit(code=1)

        for yaml_path in files_to_process:
            if "original" in yaml_path.name:
                print(f"Skipping backup file: {yaml_path.name}")
                continue
            if "runtime_symbols" in yaml_path.name:
                print(f"Skipping runtime symbols file: {yaml_path.name}")
                continue
            await _cleanup_single_yaml(
                yaml_path, beckhoff_client, FileService, composite_types
            )

    elif file is not None:
        if not file.exists():
            print(f"File not found: {file}", file=sys.stderr)
            raise typer.Exit(code=1)
        await _cleanup_single_yaml(file, beckhoff_client, FileService, composite_types)

    else:
        print("Please provide a file or use --all to process all files.")
        raise typer.Exit(code=1)


async def _cleanup_single_yaml(
    yaml_path: Path,
    beckhoff_client,
    file_service,
    composite_types,
) -> None:
    """Clean up a single YAML file.

    Converts primitive symbols to composite symbols where applicable.
    """
    print(f"Processing: {yaml_path.name}")

    # Load the YAML file
    config = file_service.open_file(yaml_path)
    print(f"  Loaded {len(config.terminal_types)} terminals")

    # Merge with XML data, converting primitives to composites
    # prefer_xml=True ensures we get fresh fastcs_name from conversion
    await file_service.merge_xml_data(
        config, beckhoff_client, composite_types, prefer_xml=True
    )

    # Select ALL symbols, but no CoE objects
    for terminal_id, terminal in config.terminal_types.items():
        selected_count = 0
        for symbol in terminal.symbol_nodes:
            symbol.selected = True
            selected_count += 1
        for coe in terminal.coe_objects:
            coe.selected = False
        print(f"  {terminal_id}: selected {selected_count} symbols, 0 CoE")

    # Save the cleaned file
    config.to_yaml(yaml_path)
    print(f"  Saved: {yaml_path.name}")


def main() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    main()
