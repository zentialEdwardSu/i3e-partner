import argparse
import os


def mount_sharing_params(parser: argparse.ArgumentParser):
    mount_cache_params(parser)
    mount_db_params(parser)
    mount_strategy_params(parser)


def mount_db_params(parser: argparse.ArgumentParser):
    """
    Mount --save/--path to the given parser
    """
    parser.add_argument(
        "--save",
        choices=["json", "db"],
        type=str,
        default=None,
        help="Save result to db or single json file",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=os.getenv("IEEE_OUTPUT_PATH"),
        help="Path to save the file, if save db, it's the path to the db file, otherwise it will overwrite the path to the json file. Default from IEEE_OUTPUT_PATH env var.",
    )


def mount_strategy_params(parser: argparse.ArgumentParser):
    """
    Mount --strategy to the given parser
    """
    parser.add_argument(
        "--strategy",
        choices=["AO", "AN", "M"],
        default=os.getenv("IEEE_STRATEGY", "AN"),
        help="Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual). Default from IEEE_STRATEGY env var or 'AN'.",
    )


def mount_cache_params(parser: argparse.ArgumentParser):
    """
    Mount --cache-ttl to the given parser
    """
    default_ttl = os.getenv("IEEE_CACHE_TTL")
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=int(default_ttl) if default_ttl else None,
        help="Cache TTL in seconds (optional). Default from IEEE_CACHE_TTL env var.",
    )


def mount_year_params(parser: argparse.ArgumentParser):
    default_start = os.getenv("IEEE_START_YEAR")
    default_end = os.getenv("IEEE_END_YEAR")

    parser.add_argument(
        "--start-year",
        type=int,
        default=int(default_start) if default_start else None,
        help="Start year. Default from IEEE_START_YEAR env var.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=int(default_end) if default_end else None,
        help="End year. Default from IEEE_END_YEAR env var.",
    )


def get_default_filter_dir():
    """Get the default filter directory from environment or fallback to ./filters"""
    return os.getenv("FILTER_DIR", "./filters")


def mount_filtering_params(parser: argparse.ArgumentParser):
    """
    Mount --keep/--exclude/--fields to the given parser
    """

    parser.add_argument(
        "--keep",
        action="append",
        help="Keep paths (dot or bracket notation). Can be repeated or comma-separated. Default from IEEE_DEFAULT_KEEP env var.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude paths (dot or bracket notation). Can be repeated or comma-separated. Default from IEEE_DEFAULT_EXCLUDE env var.",
    )
    parser.add_argument(
        "--fields",
        action="append",
        help="Shorthand fields (dot notation) to keep, e.g. authors[].author_id. Default from IEEE_DEFAULT_FIELDS env var.",
    )


def mount_filter_dir_params(parser: argparse.ArgumentParser):
    """Mount filter directory parameter"""
    parser.add_argument(
        "--filter-dir",
        type=str,
        default=get_default_filter_dir(),
        help=f"Directory to search for filter files. Default from FILTER_DIR env var or '{get_default_filter_dir()}'.",
    )
