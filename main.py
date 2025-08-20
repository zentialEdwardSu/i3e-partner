from playwright.sync_api import sync_playwright
import sys
import argparse
import logging
from cli.cli_hello import HelloPlugin
from cli.cli_db import DBPlugin
from cli.cli_ieee import IEEEPlugin
from cli.cli_cache import CachePlugin

# Manually register plugins here
plugins = {
    "hello": HelloPlugin,
    "db": DBPlugin,
    "ieee": IEEEPlugin,
    "cache": CachePlugin,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_help():
    print("Available CLI commands:")
    for name, cls in plugins.items():
        print(f"  {name:15} {getattr(cls, 'description', '')}")


def main():
    parser = argparse.ArgumentParser(description="IEEE Crawler CLI")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )
    subparsers = parser.add_subparsers(dest="command", help="sub-command help")

    # Register plugin subcommands
    for name, cls in plugins.items():
        subparser = subparsers.add_parser(
            name,
            help=f"{getattr(cls, 'description', '')}, use {name} --help for more info",
        )
        if hasattr(cls, "add_arguments"):
            cls.add_arguments(subparser)

    if len(sys.argv) < 2:
        print_help()
        return

    args = parser.parse_args()
    logger.setLevel(args.log_level)
    cmd = args.command
    if cmd in plugins:
        plugin = plugins[cmd](logger=logger)
        plugin.run(args)
    else:
        print(f"Unknown command: {cmd}")
        print_help()


if __name__ == "__main__":
    main()
