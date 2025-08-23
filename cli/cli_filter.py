import json
import logging
import os
import sys
from .cli_plugin_base import CLIPluginBase
from .params_mounter import mount_filtering_params, mount_filter_dir_params
from utils.objfilter import build_spec_from_args, filter_structure
from pathlib import Path


class FilterPlugin(CLIPluginBase):
    name = "filter"
    description = "Create, save and apply filters for data structures"

    @staticmethod
    def add_arguments(parser):
        subparsers = parser.add_subparsers(
            dest="filter_command", help="Filter sub-commands"
        )

        # create filter
        create_parser = subparsers.add_parser("create", help="Create a new filter")
        mount_filtering_params(create_parser)
        mount_filter_dir_params(create_parser)
        create_parser.add_argument(
            "--name", type=str, help="Optional name for the filter"
        )
        create_parser.add_argument(
            "--description", type=str, help="Optional description for the filter"
        )

        # apply filter
        apply_parser = subparsers.add_parser("apply", help="Apply a saved filter")
        mount_filter_dir_params(apply_parser)
        apply_parser.add_argument(
            "--filter-name", type=str, required=True, help="Name of the filter to apply"
        )
        apply_parser.add_argument(
            "--input",
            type=str,
            help="Input JSON file to filter (if not provided, reads from stdin)",
        )
        apply_parser.add_argument(
            "--output",
            type=str,
            help="Output JSON file (if not provided, writes to stdout)",
        )

        # list filters
        list_parser = subparsers.add_parser("list", help="List available filters")
        mount_filter_dir_params(list_parser)

    def __init__(self, logger=None):
        super().__init__(logger)

    def _create_filter(self, args, logger):
        """Create and optionally save a filter specification"""
        spec = build_spec_from_args(args)

        if not spec:
            logger.warning(
                "No filtering parameters provided. Use --keep, --exclude, or --fields."
            )
            return

        # Add metadata
        filter_data = {
            "spec": spec,
            "metadata": {
                "name": getattr(args, "name", None),
                "description": getattr(args, "description", None),
                "created_at": self._get_current_timestamp(),
            },
        }

        logger.info("Filter specification created:")
        logger.info(json.dumps(filter_data, ensure_ascii=False, indent=2))

        self._save_filter(filter_data, args.filter_dir, logger)

    def _save_filter(self, filter_data, dir, logger):
        """Save filter specification to file"""
        try:
            # Ensure directory exists
            os.makedirs(dir, exist_ok=True)
            path = Path(dir) / f"{filter_data['metadata']['name']}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(filter_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Filter saved to: {path}")
        except Exception as e:
            logger.error(f"Failed to save filter: {e}")
            raise

    def _load_filter(self, path, logger):
        """Load filter specification from file"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                filter_data = json.load(f)

            if "spec" not in filter_data:
                raise ValueError("Invalid filter file: missing 'spec' field")

            return filter_data
        except Exception as e:
            logger.error(f"Failed to load filter from {path}: {e}")
            raise

    def _apply_filter(self, args, logger):
        """Apply a saved filter to input data"""
        # Load filter
        filter_path = Path(args.filter_dir) / f"{args.filter_name}.json"
        filter_data = self._load_filter(filter_path, logger)
        spec = filter_data["spec"]

        # Load input data
        if hasattr(args, "input") and args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Input data loaded from: {args.input}")
        else:
            logger.info("Reading from stdin...")
            data = json.load(sys.stdin)
            logger.debug("Input data loaded from stdin")

        # Apply filter
        filtered_data, filterd = filter_structure(data, spec)
        if filterd == 0:
            logger.warning("Filter did not modify the input data.")

        # Output result
        if hasattr(args, "output") and args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(filtered_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Filtered data saved to: {args.output}")
        else:
            print(json.dumps(filtered_data, ensure_ascii=False, indent=2))

    def _list_filters(self, args, logger):
        """List available filter files"""
        filter_dir = getattr(args, "filter_dir", "./filters")

        if not os.path.exists(filter_dir):
            logger.warning(f"Filter directory does not exist: {filter_dir}")
            return

        filters = []
        for filename in os.listdir(filter_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(filter_dir, filename)
                try:
                    filter_data = self._load_filter(filepath, logger)
                    metadata = filter_data.get("metadata", {})
                    filters.append(
                        {
                            "file": filename,
                            "path": filepath,
                            "name": metadata.get("name"),
                            "description": metadata.get("description"),
                            "created_at": metadata.get("created_at"),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to load filter {filename}: {e}")

        if not filters:
            logger.info("No filter files found.")
            return

        logger.info("Available filters:")
        for f in filters:
            logger.info(f"  {f['file']}")
            if f["name"]:
                logger.info(f"    Name: {f['name']}")
            if f["description"]:
                logger.info(f"    Description: {f['description']}")
            if f["created_at"]:
                logger.info(f"    Created: {f['created_at']}")
            logger.info(f"    Path: {f['path']}")

    def _get_current_timestamp(self):
        """Get current timestamp as ISO string"""
        from datetime import datetime

        return datetime.now().isoformat()

    def run(self, args):
        logger = self.logger or logging.getLogger(__name__)

        try:
            if args.filter_command == "create":
                self._create_filter(args, logger)
            elif args.filter_command == "apply":
                self._apply_filter(args, logger)
            elif args.filter_command == "list":
                self._list_filters(args, logger)
            else:
                logger.error("No filter sub-command specified. Use --help for usage.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
