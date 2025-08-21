import db
import utils
from .cli_plugin_base import CLIPluginBase
from dataclasses import asdict
from datetime import datetime
from ieee import AuthorPage, PublicationPage
from playwright.sync_api import sync_playwright
import logging
from cache import Cacher, make_cache_key
from .params_mounter import mount_filtering_params
from utils.objfilter import filter_structure, build_spec_from_args


class DBPlugin(CLIPluginBase):
    name = "db"
    description = """
        Interact with the database
    """

    @staticmethod
    def add_arguments(parser):
        subparsers = parser.add_subparsers(dest="db_command", help="DB sub-commands")

        # init
        subparsers.add_parser("init", help="Initialize the database")

        # export
        export_parser = subparsers.add_parser("export", help="Export database to JSON")
        export_parser.add_argument(
            "--output", type=str, required=True, help="Output JSON file path"
        )
        export_parser.add_argument("--db-path", type=str, help="Database path")
        # new export filtering options
        mount_filtering_params(export_parser)

        # list
        list_parser = subparsers.add_parser("list", help="List authors or papers")
        list_parser.add_argument(
            "which", choices=["authors", "papers"], help="What to list"
        )
        list_parser.add_argument("--db-path", type=str, help="Database path")
        # new list filtering options
        mount_filtering_params(list_parser)

        # unchecked
        unchecked_parser = subparsers.add_parser(
            "unchecked", help="List IDs with check != 1 (authors or papers)"
        )
        unchecked_parser.add_argument(
            "which", choices=["authors", "papers", "all"], help="What to check"
        )
        unchecked_parser.add_argument("--db-path", type=str, help="Database path")

        # get
        choices = [
            "author_by_id",
            "author_by_name",
            "paper_by_id",
            "paper_by_doi",
            "paper_by_title",
            "papers_by_author_id",
            "papers_by_author_name",
            "authors_by_paper_id",
        ]
        get_parser = subparsers.add_parser("get", help="Query authors or papers")
        get_parser.add_argument(
            "type",
            choices=choices,
            help="Query type",
        )
        get_parser.add_argument("value", help="Query value")
        get_parser.add_argument("--db-path", type=str, help="Database path")
        # new get filtering options
        mount_filtering_params(get_parser)

        # complete
        complete_parser = subparsers.add_parser(
            "complete",
            help="Fetch and complete missing info for authors or papers (check != 1)",
        )
        complete_parser.add_argument(
            "which", choices=["authors", "papers", "all"], help="Which type to complete"
        )
        complete_parser.add_argument("--db-path", type=str, help="Database path")
        complete_parser.add_argument(
            "--strategy",
            choices=["AO", "AN", "M"],
            default="AN",
            help="Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)",
        )
        complete_parser.add_argument(
            "--start-year", type=int, help="Start year for published work list"
        )
        complete_parser.add_argument(
            "--end-year", type=int, help="End year for published work list"
        )

        # tabpub: create stub paper rows (only id) for all publications of an author
        tabpub_parser = subparsers.add_parser(
            "tabpub",
            help="Create stub paper rows (only id) for all publications of an author",
        )
        tabpub_parser.add_argument("--author-id", required=True, help="Author ID")
        tabpub_parser.add_argument("--db-path", type=str, help="Database path")
        tabpub_parser.add_argument(
            "--start-year", type=int, help="Start year to filter publications"
        )
        tabpub_parser.add_argument(
            "--end-year", type=int, help="End year to filter publications"
        )
        tabpub_parser.add_argument(
            "--cache-ttl",
            type=int,
            default=None,
            help="Cache TTL in seconds (optional) for publist",
        )

    def __init__(self, logger=None):
        super().__init__(logger)

    def run(self, args):
        import json

        # helper to build spec from args

        # create cacher for reusing fetched results
        cacher = Cacher(default_ttl=3600)

        if args.db_command == "init":
            db.init_db(db_path=getattr(args, "db_path", None))
            print("Database initialized.")
        elif args.db_command == "export":
            # replace export behavior to support filtering
            db_path = getattr(args, "db_path", None)
            spec = build_spec_from_args(args)
            # get full export structure
            authors = [to_dict(a) for a in db.get_all_authors(db_path=db_path)]
            papers = [to_dict(p) for p in db.get_all_papers(db_path=db_path)]
            export_obj = {"authors": authors, "papers": papers}
            if spec:
                # apply spec to entire export object
                export_obj = filter_structure(export_obj, spec)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(export_obj, f, ensure_ascii=False, indent=2)
            print(f"Database exported to {args.output}")
        elif args.db_command == "list":
            db_path = getattr(args, "db_path", None)
            spec = build_spec_from_args(args)
            if args.which == "authors":
                items = db.get_all_authors(db_path=db_path)
            else:
                items = db.get_all_papers(db_path=db_path)
            data = [utils.to_dict(i) for i in items]
            if spec:
                data = [filter_structure(d, spec) for d in data]
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif args.db_command == "unchecked":
            db_path = getattr(args, "db_path", None)

            which = args.which
            if which == "authors":
                ids = db.get_unchecked_authors(db_path=db_path)
                print(json.dumps(ids, ensure_ascii=False, indent=2))
            elif which == "papers":
                ids = db.get_unchecked_papers(db_path=db_path)
                print(json.dumps(ids, ensure_ascii=False, indent=2))
            else:  # all
                authors = db.get_unchecked_authors(db_path=db_path)
                papers = db.get_unchecked_papers(db_path=db_path)
                print(
                    json.dumps(
                        {"authors": authors, "papers": papers},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        elif args.db_command == "get":
            db_path = args.db_path
            t = args.type
            v = args.value
            if t == "author_by_id":
                result = db.get_author_by_id(v, db_path=db_path)
            elif t == "author_by_name":
                result = db.get_author_by_name(v, db_path=db_path)
            elif t == "paper_by_id":
                result = db.get_paper_by_id(v, db_path=db_path)
            elif t == "paper_by_doi":
                result = db.get_paper_by_doi(v, db_path=db_path)
            elif t == "paper_by_title":
                result = db.get_paper_by_title(v, db_path=db_path)
            elif t == "papers_by_author_id":
                result = db.get_papers_by_author_id(v, db_path=db_path)
            elif t == "papers_by_author_name":
                result = db.get_papers_by_author_name(v, db_path=db_path)
            elif t == "authors_by_paper_id":
                result = db.get_authors_by_paper_id(v, db_path=db_path)
            else:
                print("Unknown get type.")
                return

            spec = build_spec_from_args(args)
            if isinstance(result, list):
                data = [utils.to_dict(r) for r in result]
                if spec:
                    data = [filter_structure(d, spec) for d in data]
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                data = utils.to_dict(result)
                if spec:
                    data = filter_structure(data, spec)
                print(json.dumps(data, ensure_ascii=False, indent=2))
        elif args.db_command == "complete":
            db_path = getattr(args, "db_path", None)
            which = args.which
            strategy = getattr(args, "strategy", "AN")
            start_year = getattr(args, "start_year", None)
            end_year = getattr(args, "end_year", None)
            logger = self.logger or logging.getLogger(__name__)

            # collect targets
            targets = []
            if which in ("authors", "all"):
                authors = db.get_unchecked_authors(db_path=db_path)
                if authors:
                    for aid in authors:
                        aobj = db.get_author_by_id(aid, db_path=db_path)
                        label = (
                            aobj.name if aobj and getattr(aobj, "name", None) else ""
                        )
                        targets.append(("author", aid, label))
            if which in ("papers", "all"):
                papers = db.get_unchecked_papers(db_path=db_path)
                if papers:
                    for pid in papers:
                        pobj = db.get_paper_by_id(pid, db_path=db_path)
                        label = (
                            pobj.title if pobj and getattr(pobj, "title", None) else ""
                        )
                        targets.append(("paper", pid, label))

            if not targets:
                print("No unchecked authors or papers found for the selected type.")
                return

            # display numbered list
            print("Found the following items (index: type id - brief):")
            for idx, (typ, idv, label) in enumerate(targets, start=1):
                print(f"{idx}: {typ} {idv} - {label}")

            # prompt selection
            selection_input = input(
                "Select indices to complete (e.g. 1,2-4,9-10). Press Enter to select ALL: "
            ).strip()
            indices = utils.parse_selection(selection_input, len(targets))
            if not indices:
                print("No valid selection made, aborting.")
                return

            # prepare playwright
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=False)
            results = {"done": [], "failed": []}
            try:
                for i in indices:
                    typ, idv, label = targets[i - 1]
                    try:
                        if typ == "author":
                            # try cache first (include year range in key)
                            key = make_cache_key(
                                "author",
                                {
                                    "author_id": idv,
                                    "start_year": start_year,
                                    "end_year": end_year,
                                },
                            )
                            cached = cacher.load(key)
                            if cached is not None:
                                logger.info(f"Cache hit for author {idv}")
                                ainfo = cached
                                # ensure publication_ids present (if not, attempt to fetch publist)
                                if not getattr(ainfo, "publication_ids", None):
                                    try:
                                        with AuthorPage(browser, idv, logger) as ap_tmp:
                                            pub_ids = ap_tmp.get_published_work_id_list(
                                                start_year=start_year, end_year=end_year
                                            )
                                    except Exception:
                                        pub_ids = []
                                    try:
                                        ainfo.publication_ids = pub_ids
                                    except Exception:
                                        pass
                            else:
                                logger.info(f"Fetching author {idv} ...")
                                with AuthorPage(browser, idv, logger) as ap:
                                    ainfo = ap.get_author_info()
                                    try:
                                        pub_ids = ap.get_published_work_id_list(
                                            start_year=start_year, end_year=end_year
                                        )
                                    except Exception:
                                        pub_ids = []
                                    if ainfo:
                                        try:
                                            ainfo.publication_ids = pub_ids
                                        except Exception:
                                            pass
                                        # cache the author object
                                        try:
                                            cacher.save(key, ainfo)
                                            logger.debug(
                                                f"Saved author {idv} to cache."
                                            )
                                        except Exception:
                                            logger.debug(
                                                "Failed to cache author.", exc_info=True
                                            )
                            if ainfo:
                                db.save_or_update_author(
                                    ainfo,
                                    db_path=db_path,
                                    strategy=strategy,
                                    logger=logger,
                                )
                                results["done"].append((typ, idv))
                            else:
                                results["failed"].append((typ, idv))
                        else:  # paper
                            # try cache first
                            key = make_cache_key("pub", {"publication_id": idv})
                            cached = cacher.load(key)
                            if cached is not None:
                                logger.info(f"Cache hit for publication {idv}")
                                pinfo = cached
                            else:
                                logger.info(f"Fetching paper {idv} ...")
                                pp = PublicationPage(browser, idv, logger)
                                pinfo = pp.fetch_info()
                                if pinfo:
                                    try:
                                        cacher.save(key, pinfo)
                                        logger.debug(f"Saved paper {idv} to cache.")
                                    except Exception:
                                        logger.debug(
                                            "Failed to cache paper.", exc_info=True
                                        )
                            if pinfo:
                                db.save_paper(
                                    pinfo,
                                    db_path=db_path,
                                    strategy=strategy,
                                    logger=logger,
                                )
                                results["done"].append((typ, idv))
                            else:
                                results["failed"].append((typ, idv))
                    except Exception as e:
                        logger.error(
                            f"Error completing {typ} {idv}: {e}", exc_info=True
                        )
                        results["failed"].append((typ, idv))
            finally:
                browser.close()
                playwright.stop()

            # summary
            print("\nComplete summary:")
            print(
                f"Completed ({len(results['done'])}): {[f'{t} {i}' for t, i in results['done']]}"
            )
            print(
                f"Failed ({len(results['failed'])}): {[f'{t} {i}' for t, i in results['failed']]})"
            )

            return
        elif args.db_command == "tabpub":
            db_path = getattr(args, "db_path", None)
            author_id = getattr(args, "author_id")
            start_year = getattr(args, "start_year", None)
            end_year = getattr(args, "end_year", None)
            cache_ttl = getattr(args, "cache_ttl", None)
            logger = self.logger or logging.getLogger(__name__)

            # Try to reuse DB-stored publication_ids when no year filter is provided
            pub_ids = []
            if start_year is None and end_year is None:
                aobj = db.get_author_by_id(author_id, db_path=db_path)
                if aobj and getattr(aobj, "publication_ids", None):
                    pub_ids = getattr(aobj, "publication_ids", []) or []
                    logger.info(
                        f"Using publication_ids from DB for author {author_id} ({len(pub_ids)} items)."
                    )

            # If no pub_ids from DB, try cache, otherwise fetch via AuthorPage
            if not pub_ids:
                key = make_cache_key(
                    "publist",
                    {
                        "author_id": author_id,
                        "start_year": start_year,
                        "end_year": end_year,
                    },
                )
                cached = cacher.load(key)
                if cached is not None:
                    logger.info(f"Cache hit for publist {author_id}")
                    pub_ids = cached
                else:
                    logger.info(
                        f"Fetching publication id list for author {author_id} ..."
                    )
                    playwright = sync_playwright().start()
                    browser = playwright.chromium.launch(headless=False)
                    try:
                        with AuthorPage(browser, author_id, logger) as ap:
                            pub_ids = ap.get_published_work_id_list(
                                start_year=start_year, end_year=end_year
                            )
                    except Exception as e:
                        logger.error(
                            f"Error fetching publist for author {author_id}: {e}",
                            exc_info=True,
                        )
                        pub_ids = []
                    finally:
                        browser.close()
                        playwright.stop()
                    if pub_ids:
                        try:
                            cacher.save(key, pub_ids, ttl=cache_ttl)
                            logger.debug(
                                f"Saved publist for author {author_id} to cache."
                            )
                        except Exception:
                            logger.debug("Failed to cache publist.", exc_info=True)

            if not pub_ids:
                print(f"No publications found for author {author_id}.")
                return

            # Insert stub papers (only id) into DB
            inserted = 0
            for pid in pub_ids:
                try:
                    # create minimal PaperMetaData; db.save_paper will insert a row with default fields
                    db.save_paper(
                        db.PaperMetaData(id=pid),
                        db_path=db_path,
                        strategy="AN",
                        logger=logger,
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(
                        f"Failed to insert stub paper {pid}: {e}", exc_info=True
                    )
            print(
                f"Processed {len(pub_ids)} publication IDs for author {author_id}, inserted/updated {inserted} stub rows."
            )
            return

        else:
            print("No db sub-command specified. Use --help for usage.")


# Example usage (comment):
# data = db.get_paper_by_id("123")
# filtered = filter_structure(asdict(data), {"keep": ["[id]","[title]","[authors][:][author_id]"]})
# print(filtered)
