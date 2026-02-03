"""Entry point for catio_terminals application."""

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer

from catio_terminals.xml.cache import XmlCache

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
    from catio_terminals.xml import parse_terminal_catalog

    print("Updating terminal database from Beckhoff server...")
    cache = XmlCache()

    try:
        # Download and extract XML files
        success = cache.download_and_extract()
        if not success:
            print("Failed to download and extract XML files", file=sys.stderr)
            raise typer.Exit(code=1)

        print(f"XML files downloaded and extracted to {cache.xml_dir}")

        # Get XML files (excluding legacy catalog with incomplete PDO definitions)
        xml_files = cache.get_terminal_xml_files()
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
    include_all_coe: Annotated[
        bool,
        typer.Option(
            "--include-all-coe",
            help="Include all CoE objects (default: exclude all CoE)",
        ),
    ] = False,
) -> None:
    """Clean up terminal YAML files by syncing with Beckhoff XML.

    This command loads YAML files, merges with XML data (dropping non-XML symbols),
    selects all symbols, and saves the cleaned file.
    """
    asyncio.run(_clean_yaml_async(file, all_files, include_all_coe))


async def _clean_yaml_async(
    file: Path | None, all_files: bool, include_all_coe: bool
) -> None:
    """Async implementation of clean-yaml command."""
    from catio_terminals.beckhoff import BeckhoffClient
    from catio_terminals.service_file import FileService

    # Initialize Beckhoff client
    beckhoff_client = BeckhoffClient()

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
            await _cleanup_single_yaml(
                yaml_path, beckhoff_client, FileService, include_all_coe
            )

    elif file is not None:
        if not file.exists():
            print(f"File not found: {file}", file=sys.stderr)
            raise typer.Exit(code=1)
        await _cleanup_single_yaml(file, beckhoff_client, FileService, include_all_coe)

    else:
        print("Please provide a file or use --all to process all files.")
        raise typer.Exit(code=1)


async def _cleanup_single_yaml(
    yaml_path: Path,
    beckhoff_client,
    file_service,
    include_all_coe: bool = False,
) -> None:
    """Clean up a single YAML file.

    Reloads symbols from XML and marks all as selected.
    """
    print(f"Processing: {yaml_path.name}")

    # Load the YAML file
    config = file_service.open_file(yaml_path)
    print(f"  Loaded {len(config.terminal_types)} terminals")

    # Merge with XML data (primitive symbols)
    # prefer_xml=True ensures we get fresh data from XML
    await file_service.merge_xml_data(config, beckhoff_client, prefer_xml=True)

    # Select ALL symbols, and optionally all CoE objects
    # For dynamic PDO terminals, only select symbols in the default group
    for terminal_id, terminal in config.terminal_types.items():
        selected_count = 0
        coe_count = 0

        if terminal.has_dynamic_pdos:
            # Get the active (or default) group's symbol indices
            active_indices = terminal.get_active_symbol_indices()
            for idx, symbol in enumerate(terminal.symbol_nodes):
                symbol.selected = idx in active_indices
                if symbol.selected:
                    selected_count += 1
            group_name = terminal.selected_pdo_group or "default"
        else:
            for symbol in terminal.symbol_nodes:
                symbol.selected = True
                selected_count += 1
            group_name = None

        for coe in terminal.coe_objects:
            coe.selected = include_all_coe
            if include_all_coe:
                coe_count += 1

        if group_name:
            print(
                f"  {terminal_id}: selected {selected_count} symbols "
                f"(PDO group: {group_name}), {coe_count} CoE"
            )
        else:
            print(
                f"  {terminal_id}: selected {selected_count} symbols, {coe_count} CoE"
            )

    # Save the cleaned file
    config.to_yaml(yaml_path)
    print(f"  Saved: {yaml_path.name}")


def main() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    main()
