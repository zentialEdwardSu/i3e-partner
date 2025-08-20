import db
from .cli_plugin_base import CLIPluginBase
from dataclasses import asdict
from datetime import datetime  # added
import re
import copy
from ieee import AuthorPage, PublicationPage
from playwright.sync_api import sync_playwright
import logging


def to_dict(obj):
    # convert dataclass/datetime/list/dict recursively to JSON-serializable
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return to_dict(asdict(obj))
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_dict(i) for i in obj]
    if hasattr(obj, "__dict__"):
        d = obj.__dict__.copy()
        return {k: to_dict(v) for k, v in d.items()}
    return obj


def _parse_path(path: str):
    # extract tokens inside [...] and convert numeric tokens to int, ':' stays as ':'
    toks = re.findall(r"\[([^\]]*)\]", path)
    res = []
    for t in toks:
        if t == ":":
            res.append(":")
        else:
            if t.isdigit():
                res.append(int(t))
            else:
                res.append(t)
    return res


def _add_path(mask: dict, tokens: list):
    # set leaf to True to indicate keep/remove whole subtree
    if not tokens:
        return
    key = tokens[0]
    if key not in mask:
        mask[key] = {}
    if len(tokens) == 1:
        mask[key] = True
        return
    if mask[key] is True:
        # already whole subtree
        return
    _add_path(mask[key], tokens[1:])


def _build_mask(paths: list) -> dict:
    mask = {}
    for p in paths or []:
        toks = _parse_path(p)
        if toks:
            _add_path(mask, toks)
    return mask


def _apply_keep(obj, mask):
    # if mask True -> keep whole obj
    if mask is True:
        return copy.deepcopy(obj)
    if isinstance(obj, dict):
        out = {}
        for k, sub in mask.items():
            # only keep keys specified in mask
            if k in obj:
                res = _apply_keep(obj[k], sub)
                out[k] = res
        return out
    if isinstance(obj, list):
        out = []
        # support ':' for all elements
        if ":" in mask:
            sub = mask[":"]
            for item in obj:
                out.append(_apply_keep(item, sub))
            return out
        # or specific indices
        for k, sub in mask.items():
            if isinstance(k, int) and 0 <= k < len(obj):
                out.append(_apply_keep(obj[k], sub))
        return out
    # primitive
    return copy.deepcopy(obj)


def _apply_exclude(obj, mask):
    # if mask True -> remove whole object
    if mask is True:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in mask:
                # if submask True -> exclude entire key
                if mask[k] is True:
                    continue
                # else recurse
                res = _apply_exclude(v, mask[k])
                if res is None:
                    continue
                out[k] = res
            else:
                # keep as is
                out[k] = copy.deepcopy(v)
        return out
    if isinstance(obj, list):
        # if mask has ':' handle all elements
        if ":" in mask:
            sub = mask[":"]
            out = []
            for item in obj:
                res = _apply_exclude(item, sub)
                if res is not None:
                    out.append(res)
            return out
        # otherwise mask may contain indices to exclude/sub-filter
        out = []
        for idx, item in enumerate(obj):
            if idx in mask:
                sub = mask[idx]
                if sub is True:
                    # exclude this index
                    continue
                res = _apply_exclude(item, sub)
                if res is not None:
                    out.append(res)
            else:
                out.append(copy.deepcopy(item))
        return out
    # primitive
    return copy.deepcopy(obj)


def filter_structure(obj, spec: dict):
    """
    Filter a Python structure (dict/list/primitive) by spec:
     spec example:
      {"keep": ["[author_id]", "[authors][:][name]"]}
      {"exclude": ["[authors][0]", "[abstract]"]}
     Rules:
      - If 'keep' present: result only contains fields specified by keep paths.
      - Else if 'exclude' present: result contains everything except fields matched by exclude paths.
      - Paths use bracket notation: [key], [index], [:] for all list elements.
    """
    if not isinstance(spec, dict) or not spec:
        return copy.deepcopy(obj)
    if "keep" in spec and spec.get("keep"):
        mask = _build_mask(spec.get("keep"))  # type: ignore
        return _apply_keep(obj, mask)
    if "exclude" in spec and spec.get("exclude"):
        mask = _build_mask(spec.get("exclude"))  # type: ignore
        return _apply_exclude(obj, mask)
    # nothing to do
    return copy.deepcopy(obj)


def _field_to_bracket(path: str) -> str:
    """
    Convert convenient dot/array notation to bracket path.
    Examples:
      "author_id" -> "[author_id]"
      "authors.author_id" -> "[authors][author_id]"
      "authors[].author_id" -> "[authors][:][author_id]"
      "authors[0].name" -> "[authors][0][name]"
      "authors[:].name" -> "[authors][:][name]"
    """
    parts = []
    # split by '.' but keep any existing [...] tokens as part
    tokens = []
    buf = ""
    for ch in path:
        if ch == ".":
            if buf != "":
                tokens.append(buf)
                buf = ""
        else:
            buf += ch
    if buf != "":
        tokens.append(buf)
    for tok in tokens:
        # handle token like name[], name[:], name[0]
        if tok.endswith("[]"):
            name = tok[:-2]
            parts.append(f"[{name}]")
            parts.append("[:]")
        elif tok.endswith("[:]") or tok.endswith("[:"):
            # allow authors[:] or authors[:]
            name = tok.split("[", 1)[0]
            parts.append(f"[{name}]")
            parts.append("[:]")
        elif "[" in tok and "]" in tok:
            # keep as is, but ensure bracket positions are separate tokens
            # e.g. authors[0] -> [authors][0]
            name, rest = tok.split("[", 1)
            index = rest.rstrip("]")
            parts.append(f"[{name}]")
            if index == ":":
                parts.append("[:]")
            elif index.isdigit():
                parts.append(f"[{index}]")
            else:
                parts.append(f"[{index}]")
        else:
            parts.append(f"[{tok}]")
    return "".join(parts)


def _collect_paths(arg_list):
    """
    Normalize input: arg_list can be None, list of strings possibly comma-separated.
    Return flattened list of bracket paths.
    """
    if not arg_list:
        return []
    out = []
    for entry in arg_list:
        if entry is None:
            continue
        # support comma-separated values in one arg
        for part in entry.split(","):
            part = part.strip()
            if not part:
                continue
            # if already looks like bracket path, keep
            if part.startswith("["):
                out.append(part)
            else:
                out.append(_field_to_bracket(part))
    return out


def parse_selection(s: str, max_index: int) -> list[int]:
    """
    Parse selection string like "1,2-4,9-10".
    Empty string or None -> select all [1..max_index].
    Returns sorted unique list of 1-based indices (clamped to [1, max_index]).
    """
    if s is None or s.strip() == "":
        return list(range(1, max_index + 1))
    parts = [p.strip() for p in s.split(",") if p.strip()]
    indices = set()
    for p in parts:
        if "-" in p:
            try:
                a_str, b_str = p.split("-", 1)
                a = int(a_str)
                b = int(b_str)
                if a > b:
                    a, b = b, a
                for i in range(max(1, a), min(max_index, b) + 1):
                    indices.add(i)
            except Exception:
                # ignore invalid segment
                continue
        else:
            try:
                i = int(p)
                if 1 <= i <= max_index:
                    indices.add(i)
            except Exception:
                # ignore invalid token
                continue
    return sorted(indices)


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
        export_parser.add_argument(
            "--keep",
            action="append",
            help="Keep paths (dot or bracket notation). Can be repeated or comma-separated.",
        )
        export_parser.add_argument(
            "--exclude",
            action="append",
            help="Exclude paths (dot or bracket notation). Can be repeated or comma-separated.",
        )
        export_parser.add_argument(
            "--fields",
            action="append",
            help="Shorthand fields (dot notation) to keep, e.g. authors[].author_id",
        )

        # list
        list_parser = subparsers.add_parser("list", help="List authors or papers")
        list_parser.add_argument(
            "which", choices=["authors", "papers"], help="What to list"
        )
        list_parser.add_argument("--db-path", type=str, help="Database path")
        # new list filtering options
        list_parser.add_argument(
            "--keep",
            action="append",
            help="Keep paths (dot or bracket notation). Can be repeated or comma-separated.",
        )
        list_parser.add_argument(
            "--exclude",
            action="append",
            help="Exclude paths (dot or bracket notation). Can be repeated or comma-separated.",
        )
        list_parser.add_argument(
            "--fields",
            action="append",
            help="Shorthand fields (dot notation) to keep, e.g. authors[].author_id",
        )

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
        get_parser.add_argument(
            "--keep",
            action="append",
            help="Keep paths (dot or bracket notation). Can be repeated or comma-separated.",
        )
        get_parser.add_argument(
            "--exclude",
            action="append",
            help="Exclude paths (dot or bracket notation). Can be repeated or comma-separated.",
        )
        get_parser.add_argument(
            "--fields",
            action="append",
            help="Shorthand fields (dot notation) to keep, e.g. authors[].author_id",
        )

        # complete (新增)
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

    def __init__(self, logger=None):
        super().__init__(logger)

    def run(self, args):
        import json

        # helper to build spec from args
        def build_spec_from_args(args):
            keep = _collect_paths(getattr(args, "keep", None) or []) + _collect_paths(
                getattr(args, "fields", None) or []
            )
            exclude = _collect_paths(getattr(args, "exclude", None) or [])
            spec = {}
            if keep:
                spec["keep"] = keep
            elif exclude:
                spec["exclude"] = exclude
            return spec if spec else None

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
            data = [to_dict(i) for i in items]
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
                data = [to_dict(r) for r in result]
                if spec:
                    data = [filter_structure(d, spec) for d in data]
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                data = to_dict(result)
                if spec:
                    data = filter_structure(data, spec)
                print(json.dumps(data, ensure_ascii=False, indent=2))
        elif args.db_command == "complete":
            db_path = getattr(args, "db_path", None)
            which = args.which
            strategy = getattr(args, "strategy", "AN")
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
            indices = parse_selection(selection_input, len(targets))
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
                            logger.info(f"Fetching author {idv} ...")
                            with AuthorPage(browser, idv, logger) as ap:
                                ainfo = ap.get_author_info()
                                # also fetch publist to make publication_ids complete
                                try:
                                    pub_ids = ap.get_published_work_id_list()
                                except Exception:
                                    pub_ids = []
                                if ainfo:
                                    try:
                                        ainfo.publication_ids = pub_ids
                                    except Exception:
                                        pass
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
                            logger.info(f"Fetching paper {idv} ...")
                            pp = PublicationPage(browser, idv, logger)
                            pinfo = pp.fetch_info()
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

        else:
            print("No db sub-command specified. Use --help for usage.")


# Example usage (comment):
# data = db.get_paper_by_id("123")
# filtered = filter_structure(asdict(data), {"keep": ["[id]","[title]","[authors][:][author_id]"]})
# print(filtered)
