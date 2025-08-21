import argparse


def mount_sharing_params(parser: argparse.ArgumentParser):
    mount_cache_params(parser)
    mount_db_params(parser)
    mount_strategy_params(parser)


def mount_db_params(parser: argparse.ArgumentParser):
    """
    Mount --save-db/--db-path to the given parser
    """
    parser.add_argument("--save-db", action="store_true", help="Save to database")
    parser.add_argument("--db-path", type=str, help="Database path")


def mount_strategy_params(parser: argparse.ArgumentParser):
    """
    Mount --strategy to the given parser
    """
    parser.add_argument(
        "--strategy",
        choices=["AO", "AN", "M"],
        default="AN",
        help="Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)",
    )


def mount_cache_params(parser: argparse.ArgumentParser):
    """
    Mount --cache-ttl to the given parser
    """
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=None,
        help="Cache TTL in seconds (optional)",
    )


def mount_year_params(parser: argparse.ArgumentParser):
    parser.add_argument("--start-year", type=int, help="Start year")
    parser.add_argument("--end-year", type=int, help="End year")


def mount_filtering_params(parser: argparse.ArgumentParser):
    """
    Mount --keep/--exclude/--fields to the given parser
    """
    parser.add_argument(
        "--keep",
        action="append",
        help="Keep paths (dot or bracket notation). Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude paths (dot or bracket notation). Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--fields",
        action="append",
        help="Shorthand fields (dot notation) to keep, e.g. authors[].author_id",
    )
