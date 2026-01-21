#!/usr/bin/env python3
"""
Standalone entry point for ADS Simulation Server.

Run with:
    python -m tests.ads_sim [options]

Options:
    --host HOST              Host address to bind to (default: 127.0.0.1)
    --port PORT              Port to listen on (default: 48898)
    --config PATH            Path to YAML config file
                             (default: ethercat_chain.yaml)
    --log-level LEVEL        Set logging level: DEBUG, INFO, WARNING, ERROR
                             (default: INFO)
    --disable-notifications  Disable the notification system to reduce
                             logging noise

Example:
    python -m tests.ads_sim --host 0.0.0.0 --port 48898 --log-level DEBUG
    python -m tests.ads_sim --disable-notifications --log-level INFO
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .server import ADSSimServer


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the server."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ADS Simulation Server for testing CATio client connections.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=48898,
        help="Port to listen on",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML configuration file for EtherCAT chain",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level",
    )
    parser.add_argument(
        "--disable-notifications",
        action="store_true",
        default=False,
        help="Disable the notification system to reduce logging noise",
    )
    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)

    # Resolve config path
    config_path: Path | None = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            return 1
    else:
        # Use default config from package
        default_config = Path(__file__).parent / "ethercat_chain.yaml"
        if default_config.exists():
            config_path = default_config
            logger.info(f"Using default config: {config_path}")

    # Create and start server
    server = ADSSimServer(
        host=args.host,
        port=args.port,
        config_path=config_path,
        enable_notifications=not args.disable_notifications,
    )

    if args.disable_notifications:
        logger.info("Notification system disabled")

    # Setup graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, shutting down...")
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await server.start()
        logger.info(f"ADS Simulation Server running on {args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop")

        # Wait for shutdown signal
        await shutdown_event.wait()

    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        return 1
    finally:
        await server.stop()

    return 0


def run() -> None:
    """Entry point for console script."""
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
