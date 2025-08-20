import os
import time
import pickle
import hashlib
from typing import Any, Optional


class Cacher:
    """
    Simple filesystem cacher using pickle.
    Save objects with an associated timestamp and ttl (seconds).
    Key is hashed to produce safe filename.
    """

    def __init__(self, cache_dir: Optional[str] = None, default_ttl: int = 3600):
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), ".ieee_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.default_ttl = default_ttl

    def _filename(self, key: str) -> str:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{h}.pkl")

    def save(self, key: str, obj: Any, ttl: Optional[int] = None) -> None:
        path = self._filename(key)
        payload = {
            "ts": time.time(),
            "ttl": (ttl if ttl is not None else self.default_ttl),
            "obj": obj,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)

    def load(self, key: str) -> Optional[Any]:
        path = self._filename(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                payload = pickle.load(f)
            ts = payload.get("ts", 0)
            ttl = payload.get("ttl", self.default_ttl)
            if ttl >= 0 and (time.time() - ts) > ttl:
                # expired
                try:
                    os.remove(path)
                except Exception:
                    pass
                return None
            return payload.get("obj")
        except Exception:
            # corrupted or unreadable
            try:
                os.remove(path)
            except Exception:
                pass
            return None

    def clear(self, key: Optional[str] = None) -> None:
        if key is None:
            # clear all
            for fn in os.listdir(self.cache_dir):
                p = os.path.join(self.cache_dir, fn)
                try:
                    os.remove(p)
                except Exception:
                    pass
        else:
            path = self._filename(key)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def cleanup(self) -> None:
        """
        Remove expired cache files.
        """
        now = time.time()
        for fn in os.listdir(self.cache_dir):
            p = os.path.join(self.cache_dir, fn)
            try:
                with open(p, "rb") as f:
                    payload = pickle.load(f)
                ts = payload.get("ts", 0)
                ttl = payload.get("ttl", self.default_ttl)
                if ttl >= 0 and (now - ts) > ttl:
                    os.remove(p)
            except Exception:
                try:
                    os.remove(p)
                except Exception:
                    pass


def make_cache_key(command: str, params: dict) -> str:
    """
    Normalize command + params dict into a deterministic key string.
    """
    # sort params for deterministic key
    parts = [command]
    for k in sorted(params.keys()):
        parts.append(f"{k}={params[k]!r}")
    return "|".join(parts)
