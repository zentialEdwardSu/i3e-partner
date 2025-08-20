from ieee import AuthorPage, PublicationPage
from .cli_plugin_base import CLIPluginBase
from dataclasses import asdict
import json
import logging
from playwright.sync_api import sync_playwright
import db
from cache import Cacher, make_cache_key
from datetime import datetime  # added


class IEEEPlugin(CLIPluginBase):
    name = "ieee"
    description = "Interact with IEEE publication and author pages"

    @staticmethod
    def add_arguments(parser):
        subparsers = parser.add_subparsers(
            dest="ieee_command", help="IEEE sub-commands"
        )

        # fetch_info
        fetch_parser = subparsers.add_parser("pub", help="Fetch publication info")
        fetch_parser.add_argument(
            "--publication-id", required=True, help="Publication ID"
        )
        fetch_parser.add_argument(
            "--save-db", action="store_true", help="Save to database"
        )
        fetch_parser.add_argument("--db-path", type=str, help="Database path")
        fetch_parser.add_argument(
            "--cache-ttl",
            type=int,
            default=None,
            help="Cache TTL in seconds (optional)",
        )
        fetch_parser.add_argument(
            "--strategy",
            choices=["AO", "AN", "M"],
            default="AN",
            help="Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)",
        )

        # get_author_info
        author_parser = subparsers.add_parser("author", help="Fetch author info")
        author_parser.add_argument("--author-id", required=True, help="Author ID")
        author_parser.add_argument(
            "--save-db", action="store_true", help="Save to database"
        )
        author_parser.add_argument("--db-path", type=str, help="Database path")
        author_parser.add_argument(
            "--no-pub-list",
            action="store_true",
            help="Do not fetch published work id list",
        )
        author_parser.add_argument("--start-year", type=int, help="Start year")
        author_parser.add_argument("--end-year", type=int, help="End year")
        author_parser.add_argument(
            "--cache-ttl",
            type=int,
            default=None,
            help="Cache TTL in seconds (optional)",
        )
        author_parser.add_argument(
            "--strategy",
            choices=["AO", "AN", "M"],
            default="AN",
            help="Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)",
        )

        # get_published_work_id_list
        pub_list_parser = subparsers.add_parser(
            "publist", help="Get published work IDs for author"
        )
        pub_list_parser.add_argument("--author-id", required=True, help="Author ID")
        pub_list_parser.add_argument("--start-year", type=int, help="Start year")
        pub_list_parser.add_argument("--end-year", type=int, help="End year")
        pub_list_parser.add_argument(
            "--save-db", action="store_true", help="Save to database"
        )
        pub_list_parser.add_argument("--db-path", type=str, help="Database path")
        pub_list_parser.add_argument(
            "--cache-ttl",
            type=int,
            default=None,
            help="Cache TTL in seconds (optional)",
        )
        pub_list_parser.add_argument(
            "--strategy",
            choices=["AO", "AN", "M"],
            default="AN",
            help="Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)",
        )

    def __init__(self, logger=None):
        super().__init__(logger)

    def run(self, args):
        logging.basicConfig(level=logging.INFO)
        logger = self.logger or logging.getLogger(__name__)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False)

        # create cacher instance (default ttl in seconds)
        cacher = Cacher(default_ttl=3600)

        def json_safe(obj):
            """
            Recursively convert dataclass/datetime/etc to JSON-serializable structures.
            """
            if obj is None:
                return None
            if isinstance(obj, datetime):
                return obj.isoformat()
            # dataclass
            if hasattr(obj, "__dataclass_fields__"):
                return json_safe(asdict(obj))
            if isinstance(obj, dict):
                return {k: json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [json_safe(i) for i in obj]
            # fallback: basic types
            return obj

        if args.ieee_command == "pub":
            key = make_cache_key("pub", {"publication_id": args.publication_id})
            cached = cacher.load(key)
            if cached is not None:
                logger.info(f"Cache hit for publication {args.publication_id}")
                info = cached
            else:
                logger.info(
                    f"Cache miss for publication {args.publication_id}, fetching"
                )
                pub = PublicationPage(browser, args.publication_id, logger)
                info = pub.fetch_info()
                if info:
                    ttl = getattr(args, "cache_ttl", None)
                    cacher.save(key, info, ttl=ttl)
                    logger.debug("Saved publication info to cache.")
            if info:
                logger.debug("Publication info ready.")
                logger.info(
                    "Publication info:\n"
                    + json.dumps(json_safe(info), ensure_ascii=False, indent=2)
                )
                if args.save_db:
                    db.save_paper(
                        info,
                        db_path=args.db_path,
                        strategy=getattr(args, "strategy", "AN"),
                        logger=logger,
                    )
                    logger.info(
                        f"Saved publication info to database (db_path={args.db_path})."
                    )
            else:
                logger.warning("No publication info found.")
        elif args.ieee_command == "author":
            # build cache key including start/end years when publist would be fetched
            key_params = {"author_id": args.author_id}
            if not getattr(args, "no_pub_list", False):
                key_params["start_year"] = getattr(args, "start_year", None)
                key_params["end_year"] = getattr(args, "end_year", None)
            key = make_cache_key("author", key_params)
            cached = cacher.load(key)
            if cached is not None:
                logger.info(f"Cache hit for author {args.author_id}")
                info = cached
                ids = getattr(info, "publication_ids", []) or []
            else:
                logger.info(f"Cache miss for author {args.author_id}, fetching")
                with AuthorPage(browser, args.author_id, logger) as author:
                    info = author.get_author_info()
                    ids = []
                    if info and not getattr(args, "no_pub_list", False):
                        ids = author.get_published_work_id_list(
                            start_year=args.start_year, end_year=args.end_year
                        )
                        # attach ids to author object
                        info.publication_ids = ids
                    # save author object (with publication_ids if present) into cache
                    ttl = getattr(args, "cache_ttl", None)
                    cacher.save(key, info, ttl=ttl)
                    logger.debug("Saved author object to cache.")
            if info:
                logger.info(
                    "Author info:\n"
                    + json.dumps(json_safe(info), ensure_ascii=False, indent=2)
                )
                if ids:
                    logger.info(
                        "Published work IDs:\n"
                        + json.dumps(json_safe(ids), ensure_ascii=False, indent=2)
                    )
                if args.save_db:
                    # use save_or_update_author to allow passing strategy
                    db.save_or_update_author(
                        info,
                        db_path=args.db_path,
                        strategy=getattr(args, "strategy", "AN"),
                        logger=logger,
                    )
                    logger.info(
                        f"Saved author info to database (db_path={args.db_path})."
                    )
            else:
                logger.warning("No author info found.")
        elif args.ieee_command == "publist":
            key = make_cache_key(
                "publist",
                {
                    "author_id": args.author_id,
                    "start_year": args.start_year,
                    "end_year": args.end_year,
                },
            )
            cached = cacher.load(key)
            if cached is not None:
                logger.info(f"Cache hit for publist {args.author_id}")
                ids = cached
            else:
                logger.info(f"Cache miss for publist {args.author_id}, fetching")
                author = AuthorPage(browser, args.author_id, logger)
                ids = author.get_published_work_id_list(
                    start_year=args.start_year, end_year=args.end_year
                )
                ttl = getattr(args, "cache_ttl", None)
                cacher.save(key, ids, ttl=ttl)
                logger.debug("Saved publist to cache.")
            logger.debug(f"Published work IDs fetched: {len(ids)} items.")
            logger.info(
                "Published work IDs:\n"
                + json.dumps(json_safe(ids), ensure_ascii=False, indent=2)
            )
            if args.save_db and ids:
                for pid in ids:
                    db.save_paper(
                        db.PaperMetaData(
                            id=pid,
                        ),
                        db_path=args.db_path,
                        strategy=getattr(args, "strategy", "AN"),
                        logger=logger,
                    )
                logger.info(
                    f"Saved {len(ids)} publication IDs to database as stub papers (db_path={args.db_path})."
                )
        else:
            logger.error("No ieee sub-command specified. Use --help for usage.")

        browser.close()
        playwright.stop()
