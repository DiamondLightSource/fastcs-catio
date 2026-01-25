"""Entry point for catio_terminals application."""

import argparse
import sys
from pathlib import Path

from catio_terminals.ui_app import run
from catio_terminals.xml_cache import XmlCache


def update_cache() -> int:
    """Update the XML cache from Beckhoff's server.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from catio_terminals.xml_parser import parse_terminal_catalog

    print("Updating terminal database from Beckhoff server...")
    cache = XmlCache()

    try:
        # Download and extract XML files
        success = cache.download_and_extract()
        if not success:
            print("✗ Failed to download and extract XML files", file=sys.stderr)
            return 1

        print(f"✓ XML files downloaded and extracted to {cache.xml_dir}")

        # Get XML files
        xml_files = cache.get_xml_files()
        print(f"✓ Found {len(xml_files)} XML files")

        # Parse terminals from XML files
        print("Parsing terminal catalog...")

        def progress_callback(message: str, progress: float) -> None:
            """Display progress updates."""
            print(f"  [{progress * 100:5.1f}%] {message}")

        terminals = parse_terminal_catalog(
            xml_files,
            progress_callback=progress_callback,
        )

        print(f"✓ Parsed {len(terminals)} terminals")

        # Save to cache
        cache.save_terminals(terminals)
        print(f"✓ Saved terminal database to {cache.terminals_file}")

        return 0

    except Exception as e:
        print(f"✗ Error updating cache: {e}", file=sys.stderr)
        return 1
    finally:
        cache.close()


def main() -> None:
    """Parse command-line arguments and run the application."""
    parser = argparse.ArgumentParser(
        description="CATio Terminal Editor - YAML terminal configuration editor"
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        default=None,
        help=(
            "YAML file to open (if not provided, a file selector dialog will be shown)"
        ),
    )
    parser.add_argument(
        "--update-cache",
        action="store_true",
        help="Update the terminal database cache from Beckhoff server and exit",
    )
    args = parser.parse_args()

    if args.update_cache:
        sys.exit(update_cache())

    run(file_path=args.file)


if __name__ == "__main__":
    main()
