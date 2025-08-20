import os
import time
import pickle
from typing import Optional
from .cli_plugin_base import CLIPluginBase
from cache import Cacher
import argparse


class CachePlugin(CLIPluginBase):
    """
    Manage local cache files created by Cacher.
    Subcommands:
      cleanup         - remove expired cache files
      clear           - remove specific cache entry by key or all entries with --all
      list            - list cache files with metadata
    """

    name = "cache"
    description = "Manage crawler cache (cleanup, clear, list)"

    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="cache_command", help="cache sub-commands")

        sub.add_parser("cleanup", help="Remove expired cache files")

        clear_p = sub.add_parser("clear", help="Clear cache entry or all entries")
        clear_p.add_argument(
            "--key", type=str, help="Cache key used when saving (raw key string)"
        )
        clear_p.add_argument("--all", action="store_true", help="Clear all cache files")
        clear_p.add_argument("--cache-dir", type=str, help="Cache directory (optional)")

        list_p = sub.add_parser("list", help="List cache entries")
        list_p.add_argument("--cache-dir", type=str, help="Cache directory (optional)")
        list_p.add_argument(
            "--show-object",
            action="store_true",
            help="Try to show brief object repr (may be large)",
        )

    def __init__(self, logger=None):
        super().__init__(logger)

    def run(self, args):
        logger = self.logger or __import__("logging").getLogger(__name__)
        cache_dir = getattr(args, "cache_dir", None)
        cacher = Cacher(cache_dir=cache_dir)

        cmd = getattr(args, "cache_command", None)
        if cmd == "cleanup":
            logger.info("Running cache cleanup (removing expired files)...")
            cacher.cleanup()
            logger.info("Cache cleanup finished.")
            return

        if cmd == "clear":
            if getattr(args, "all", False):
                logger.info(f"Clearing all cache files in {cacher.cache_dir} ...")
                cacher.clear(None)
                logger.info("All cache files cleared.")
                return
            if getattr(args, "key", None):
                key = args.key
                logger.info(f"Clearing cache entry for key: {key} ...")
                cacher.clear(key)
                logger.info("Cache entry cleared (if existed).")
                return
            logger.error("clear requires --key or --all")
            return

        if cmd == "list":
            logger.info(f"Listing cache files in {cacher.cache_dir} ...")
            files = sorted(os.listdir(cacher.cache_dir))
            entries = []
            for fn in files:
                path = os.path.join(cacher.cache_dir, fn)
                info = {"file": fn}
                try:
                    st = os.stat(path)
                    info["size"] = str(st.st_size)
                    info["mtime"] = time.ctime(st.st_mtime)
                    with open(path, "rb") as f:
                        payload = pickle.load(f)
                    # guard payload type
                    if not isinstance(payload, dict):
                        info["error"] = "invalid payload type"
                    else:
                        ts = payload.get("ts", 0)
                        ttl = payload.get("ttl", None)
                        info["age_seconds"] = str(int(time.time() - ts))
                        info["ttl"] = str(ttl)
                        if ttl is None or ttl < 0:
                            info["expires_in"] = "never"
                        else:
                            info["expires_in"] = str(int(ttl - (time.time() - ts)))
                        if getattr(args, "show_object", False):
                            try:
                                obj = payload.get("obj")
                                info["obj_type"] = type(obj).__name__
                            except Exception:
                                info["obj_type"] = "unreadable"
                except Exception as e:
                    info["error"] = str(e)
                entries.append(info)
            for e in entries:
                parts = [f"{e.get('file')}"]
                if "size" in e:
                    parts.append(f"size={e['size']}")
                if "age_seconds" in e:
                    parts.append(f"age={e['age_seconds']}s")
                if "ttl" in e:
                    parts.append(f"ttl={e['ttl']}")
                if "expires_in" in e:
                    parts.append(f"expires_in={e['expires_in']}")
                if "obj_type" in e:
                    parts.append(f"obj={e['obj_type']}")
                if "error" in e:
                    parts.append(f"error={e['error']}")
                logger.info(" | ".join(parts))
            logger.info(f"Total cache files: {len(entries)}")
            return

        logger.error("No cache sub-command specified. Use --help for usage.")
