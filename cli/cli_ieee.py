import random
import typing
from T import IEEEAuthor, PaperMetaData
from ieee import AuthorPage, PublicationPage
import utils as utils
from .cli_plugin_base import CLIPluginBase
import json
import logging
from playwright.sync_api import sync_playwright
from cache import Cacher, make_cache_key
from .params_mounter import (
    mount_year_params,
    mount_sharing_params,
)
import time


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
        mount_sharing_params(fetch_parser)

        # get_author_info
        author_parser = subparsers.add_parser("author", help="Fetch author info")
        author_parser.add_argument("--author-id", required=True, help="Author ID")
        author_parser.add_argument(
            "--no-pub-list",
            action="store_true",
            help="Do not fetch published works' information list",
        )
        mount_year_params(author_parser)
        mount_sharing_params(author_parser)

        # get_published_work_id_list
        pub_list_parser = subparsers.add_parser(
            "publist", help="Get published work IDs for author"
        )
        pub_list_parser.add_argument("--author-id", required=True, help="Author ID")
        mount_year_params(pub_list_parser)
        mount_sharing_params(pub_list_parser)

    def __init__(self, logger=None):
        super().__init__(logger)

    def get_one_pub_with_cache(
        self,
        publication_id: str,
        browser,
        cacher: Cacher,
        logger: logging.Logger,
        cache_ttl: typing.Optional[int] = None,
        hold: bool = True,
    ) -> typing.Optional[PaperMetaData]:
        """
        get publication info with caching
        Args:
            publication_id: The ID of the publication to fetch
            browser: The Playwright browser instance
            cacher: The cache manager instance
            logger: The logger instance
            cache_ttl: Optional cache TTL
            hold: Whether to hold on to avoid rate limit (default True)
        Return:
            The publication info
        """
        pubinfo: PaperMetaData = PaperMetaData()
        key = make_cache_key("pub", {"publication_id": publication_id})
        cached = cacher.load(key)
        if cached is not None:
            logger.info(f"Cache hit for publication {publication_id}")
            pubinfo = cached
        else:
            logger.info(f"Cache miss for publication {publication_id}, fetching")
            if hold:
                st = random.randint(25, 35)
                logger.info(f"Wait {st} seconds before fetching to avoid rate limit.")
                time.sleep(st)  # Sleep for 20-40 seconds
            pubpage = PublicationPage(browser, publication_id, logger)
            pubinfo = pubpage.fetch_info()  # type: ignore
            if pubinfo:
                cacher.save(key, pubinfo, ttl=cache_ttl)
                logger.debug("Saved publication info to cache.")

        return pubinfo

    def _run_pub(self, args, browser, cacher: Cacher, logger: logging.Logger):
        """Handle pub subcommand"""
        logger.info(f"Fetching publication {args.publication_id}")
        pubinfo = self.get_one_pub_with_cache(
            args.publication_id, browser, cacher, logger, args.cache_ttl, False
        )
        if pubinfo:
            # ensure check present (PublicationPage already computes, but guard)
            try:
                pubinfo.check = utils._compute_paper_check(pubinfo)
            except Exception:
                pubinfo.check = getattr(pubinfo, "check", 0)
            d_info = utils.to_dict(pubinfo)
            logger.info(
                "Publication info:\n" + json.dumps(d_info, ensure_ascii=False, indent=2)
            )
            p = args.path or f"{pubinfo.id}.json"
            self._save_to(args.save, None, d_info, p, logger)  # type: ignore
        else:
            logger.warning(f"No info for publication {args.publication_id} found.")

    def _run_author(self, args, browser, cacher, logger):
        """Handle author subcommand"""
        # build cache key including start/end years when publist would be fetched
        download_pubs = not getattr(args, "no_pub_list", False)
        start_year = getattr(args, "start_year", None)
        end_year = getattr(args, "end_year", None)
        key_params = {
            "author_id": args.author_id,
            "start_year": start_year,
            "end_year": end_year,
            "download_pubs": download_pubs,
        }
        key = make_cache_key("author", key_params)
        cached = cacher.load(key)
        ttl = getattr(args, "cache_ttl", None)
        ids = []
        pubs: list[PaperMetaData] = []
        author_info: IEEEAuthor = IEEEAuthor()

        if cached is not None:
            logger.info(f"Cache hit for author {args.author_id}")
            author_info = cached
            ids = getattr(author_info, "publication_ids", []) or []
        else:
            logger.info(f"Cache miss for author {args.author_id}, fetching")
            with AuthorPage(browser, args.author_id, logger) as author:
                author_info = author.get_author_info()  # type: ignore
                if author_info:
                    ids = author.get_published_work_id_list(
                        start_year=args.start_year, end_year=args.end_year
                    )
                    # attach ids to author object
                    author_info.publication_ids = ids
                    # compute check for author now that publication_ids are attached
                    try:
                        author_info.check = utils._compute_author_check(author_info)
                    except Exception:
                        author_info.check = getattr(author_info, "check", 0)
                # cache/save will include info.check
        cacher.save(key, author_info, ttl=ttl)
        logger.debug(
            f"Saved author {author_info.name}_{author_info.author_id} object to cache."
        )

        error_pubid: list[str] = []
        if download_pubs and ids:
            # fetch publication info for each ID
            for i, pub_id in enumerate(ids):
                logger.info(f"Fetching publication {i + 1}/{len(ids)}: {pub_id}")
                pubinfo = self.get_one_pub_with_cache(
                    pub_id, browser, cacher, logger, ttl
                )
                if pubinfo:
                    pubs.append(pubinfo)
                else:
                    error_pubid.append(pub_id)
            logger.info(
                f"Fetched {len(pubs)}/{len(ids)} publications, errors ids: {error_pubid}"
            )
        else:
            logger.debug(
                f"Skipping fetching publication info list.download_pubs={download_pubs}, ids={ids}"
            )

        if (
            args.save in ["db", "json"]
            and author_info
            and (download_pubs and pubs != [])
        ):
            path = (
                args.path
                or f"{author_info.author_id}_{author_info.name}_{f'{start_year}_{end_year}' if start_year and end_year else ''}.json"
            )
            self._save_to(args.save, author_info, pubs, path, logger)
        else:
            logger.debug(
                f"Can't save: args.save={args.save}, author_info={author_info}, download_pubs={download_pubs}, pubs={pubs}"
            )

        if author_info:
            if args.save is not None:
                logger.info("No console output when --save is used.")
                return

            author_dict = utils.to_dict(author_info)
            logger.info(
                "Author info:\n" + json.dumps(author_dict, ensure_ascii=False, indent=2)
            )

            ids_dict = utils.to_dict(ids)
            logger.info(
                "Published work IDs:\n"
                + json.dumps(ids_dict, ensure_ascii=False, indent=2)
            )
            if download_pubs and pubs:
                pubs_dict = utils.to_dict(pubs)
                logger.info(
                    "Published works' information list:\n"
                    + json.dumps(pubs_dict, ensure_ascii=False, indent=2)
                )

        else:
            logger.warning("No author info found.")

    def _run_publist(self, args, browser, cacher, logger):
        """Handle publist subcommand"""
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
            + json.dumps(utils.to_dict(ids), ensure_ascii=False, indent=2)
        )
        if args.save_db and ids:
            logger.warning("Save to db is temporarily disabled.")

    def _save_to(
        self,
        to: str,
        author_info: typing.Optional[IEEEAuthor],
        publications: typing.Optional[list[PaperMetaData]],
        path: str,
        logger,
    ):
        if to == "db":
            logger.warning("Save to db is temporarily disabled.")
        elif to == "json":
            logger.info(f"Saving to JSON file: {path}")
            data = {}
            if author_info is not None and publications is not None:
                data = utils.to_dict(typing.cast(IEEEAuthor, author_info))
                data["publications"] = utils.to_dict(publications)  # type: ignore
                del data["check"]  # remove redundant check # type: ignore
                del data["publication_ids"]  # remove redundant ids list # type: ignore
            elif author_info is not None:
                data = utils.to_dict(typing.cast(IEEEAuthor, author_info))
            elif publications is not None:
                data = utils.to_dict(publications)
            else:
                raise ValueError(
                    "No data to save, both author_info and publications are None."
                )
            # Save to JSON file
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif to is None:
            pass  # if none, no save needed
        else:
            raise ValueError(f"Unknown save option: {to}, expected 'db' or 'json'.")

    def run(self, args):
        logging.basicConfig(level=logging.INFO)
        logger = self.logger or logging.getLogger(__name__)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False)

        # create cacher instance (default ttl in seconds)
        cacher = Cacher(default_ttl=86400)

        try:
            if args.ieee_command == "pub":
                self._run_pub(args, browser, cacher, logger)
            elif args.ieee_command == "author":
                self._run_author(args, browser, cacher, logger)
            elif args.ieee_command == "publist":
                self._run_publist(args, browser, cacher, logger)
            else:
                logger.error("No ieee sub-command specified. Use --help for usage.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
        finally:
            browser.close()
            playwright.stop()
            logger.debug("Closing browser and stopping Playwright.")
