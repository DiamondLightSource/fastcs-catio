"""Entry point for catio_terminals application."""

import sys
from pathlib import Path
from typing import Annotated

import typer

from catio_terminals.ui_app import run
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


def main() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    main()
