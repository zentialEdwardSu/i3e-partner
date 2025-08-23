import json
import logging
import sys
import os
from pathlib import Path
from .cli_plugin_base import CLIPluginBase


class JSONPlugin(CLIPluginBase):
    name = "json"
    description = "JSON processing utilities"

    @staticmethod
    def add_arguments(parser):
        subparsers = parser.add_subparsers(
            dest="json_command", help="JSON sub-commands"
        )

        # to-markdown command
        md_parser = subparsers.add_parser("md", help="Convert JSON to Markdown")
        md_parser.add_argument(
            "-i",
            "--input",
            type=str,
            help="Input JSON file (if not provided, reads from stdin)",
        )
        md_parser.add_argument(
            "-o",
            "--output",
            type=str,
            help="Output Markdown file (if not provided, auto-generates or writes to stdout)",
        )
        md_parser.add_argument(
            "--title",
            type=str,
            help="Title for the Markdown document (defaults to input filename if -i provided)",
        )
        md_parser.add_argument(
            "--max-depth",
            type=int,
            default=6,
            help="Maximum depth for nested structures (default: 6)",
        )

        # compress command
        compress_parser = subparsers.add_parser(
            "compress", help="Compress JSON by removing unnecessary whitespace"
        )
        compress_parser.add_argument(
            "-i",
            "--input",
            type=str,
            help="Input JSON file (if not provided, reads from stdin)",
        )
        compress_parser.add_argument(
            "-o",
            "--output",
            type=str,
            help="Output JSON file (if not provided, auto-generates or writes to stdout)",
        )

    def __init__(self, logger=None):
        super().__init__(logger)

    def _get_auto_output_path(self, input_path, command_type):
        """Generate automatic output filename based on input path and command type"""
        input_path = Path(input_path)
        stem = input_path.stem

        if command_type == "compress":
            return f"compressed_{stem}.json"
        elif command_type == "markdown":
            return f"{stem}.md"

        return None

    def _get_default_title(self, input_path):
        """Get default title from input filename"""
        if input_path:
            return Path(input_path).stem
        return "JSON Data"

    def _to_markdown(self, args, logger):
        """Convert JSON to Markdown format"""
        # Load input data
        if hasattr(args, "input") and args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Input data loaded from: {args.input}")
        else:
            logger.info("Reading from stdin...")
            data = json.load(sys.stdin)
            logger.debug("Input data loaded from stdin")

        # Determine title
        title = (
            args.title
            if args.title
            else self._get_default_title(getattr(args, "input", None))
        )

        # Convert to markdown
        markdown_content = self._json_to_markdown(data, title, args.max_depth)

        # Determine output path
        output_path = args.output
        if not output_path and hasattr(args, "input") and args.input:
            output_path = self._get_auto_output_path(args.input, "markdown")
            logger.info(f"Auto-generated output filename: {output_path}")

        # Output result
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info(f"Markdown saved to: {output_path}")
        else:
            print(markdown_content)

    def _compress_json(self, args, logger):
        """Compress JSON by removing unnecessary whitespace"""
        # Load input data
        if hasattr(args, "input") and args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Input data loaded from: {args.input}")
        else:
            logger.info("Reading from stdin...")
            data = json.load(sys.stdin)
            logger.debug("Input data loaded from stdin")

        # Compress JSON (no indentation, no separators)
        compressed_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

        # Determine output path
        output_path = args.output
        if not output_path and hasattr(args, "input") and args.input:
            output_path = self._get_auto_output_path(args.input, "compress")
            logger.info(f"Auto-generated output filename: {output_path}")

        # Output result
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(compressed_json)
            logger.info(f"Compressed JSON saved to: {output_path}")
        else:
            print(compressed_json)

    def _json_to_markdown(self, data, title="JSON Data", max_depth=6):
        """Convert JSON data to Markdown format"""
        markdown = [f"# {title}\n"]

        def _convert_value(value, depth=1):
            if depth > max_depth:
                return f"*(max depth {max_depth} reached)*"

            if isinstance(value, dict):
                if not value:
                    return "*empty object*"
                lines = []
                for key, val in value.items():
                    lines.append(f"{'#' * min(depth + 1, 6)} {key}\n")
                    converted = _convert_value(val, depth + 1)
                    if isinstance(val, (dict, list)) and val:
                        lines.append(converted)
                    else:
                        lines.append(f"{converted}\n")
                return "\n".join(lines)

            elif isinstance(value, list):
                if not value:
                    return "*empty array*"
                lines = []
                for i, item in enumerate(value):
                    if isinstance(item, (dict, list)):
                        lines.append(f"{'#' * min(depth + 1, 6)} Item {i + 1}\n")
                        lines.append(_convert_value(item, depth + 1))
                    else:
                        lines.append(f"- {_convert_value(item, depth + 1)}")
                return "\n".join(lines)

            elif isinstance(value, str):
                # Escape markdown special characters
                escaped = (
                    value.replace("`", "\\`").replace("*", "\\*").replace("_", "\\_")
                )
                if "\n" in escaped:
                    return f"```\n{escaped}\n```"
                return f"`{escaped}`"

            elif value is None:
                return "*null*"

            elif isinstance(value, bool):
                return f"**{str(value).lower()}**"

            else:
                return f"`{str(value)}`"

        markdown.append(_convert_value(data))
        return "\n".join(markdown)

    def run(self, args):
        logger = self.logger or logging.getLogger(__name__)

        try:
            if args.json_command == "md":
                self._to_markdown(args, logger)
            elif args.json_command == "compress":
                self._compress_json(args, logger)
            else:
                logger.error("No JSON sub-command specified. Use --help for usage.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
