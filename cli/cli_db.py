import db
from .cli_plugin_base import CLIPluginBase
from dataclasses import asdict
from datetime import datetime  # added


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

        # list
        list_parser = subparsers.add_parser("list", help="List authors or papers")
        list_parser.add_argument(
            "which", choices=["authors", "papers"], help="What to list"
        )
        list_parser.add_argument("--db-path", type=str, help="Database path")

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

    def __init__(self, logger=None):
        super().__init__(logger)

    def run(self, args):
        if args.db_command == "init":
            db.init_db(db_path=getattr(args, "db_path", None))
            print("Database initialized.")
        elif args.db_command == "export":
            db.export_db(args.output, db_path=args.db_path)
            print(f"Database exported to {args.output}")
        elif args.db_command == "list":
            db_path = getattr(args, "db_path", None)
            import json

            if args.which == "authors":
                items = db.get_all_authors(db_path=db_path)
            else:
                items = db.get_all_papers(db_path=db_path)

            print(json.dumps([to_dict(i) for i in items], ensure_ascii=False, indent=2))
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
            import json

            if isinstance(result, list):
                print(
                    json.dumps(
                        [to_dict(r) for r in result], ensure_ascii=False, indent=2
                    )
                )
            else:
                print(json.dumps(to_dict(result), ensure_ascii=False, indent=2))
        else:
            print("No db sub-command specified. Use --help for usage.")
