"""Entry point for catio_terminals application."""

import argparse
from pathlib import Path

from catio_terminals.ui_app import run


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
    args = parser.parse_args()

    run(file_path=args.file)


if __name__ == "__main__":
    main()
