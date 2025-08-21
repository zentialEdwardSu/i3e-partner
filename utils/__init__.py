from dataclasses import asdict
from datetime import datetime
import random
from playwright.sync_api import Page
from playwright.sync_api import Error
import typing


T = typing.TypeVar("T")


def to_dict(obj):
    # convert dataclass/datetime/list/dict recursively to JSON-serializable
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.strftime("%d %B %Y")
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


def random_wait(page: Page, min_seconds=2, max_seconds=5):
    wait_time = random.uniform(min_seconds, max_seconds)
    page.wait_for_timeout(wait_time * 1000)


def has_access(page: Page) -> bool:
    return page.query_selector("div.inst-name") is not None


# Try to let type system happy
def remove_none(s: typing.Optional[T], default_value: T) -> T:
    return s if s is not None else default_value


def retry_with_exponential_backoff(func, max_retries=3, base_delay=2):
    import time

    for attempt in range(max_retries):
        try:
            return func()
        except Error as e:
            if attempt == max_retries - 1:
                raise e
            delay = base_delay * (2**attempt)
            print(
                f"Playwright NetWork Error, R: ({attempt + 1}/{max_retries}), W{delay}: {e}"
            )
            time.sleep(delay)


def _is_default(val):
    return val is None or val == "" or val == [] or val == {}


def _compute_author_check(author):
    name = getattr(author, "name", None)
    aff = getattr(author, "affiliation", None)
    pubids = getattr(author, "publication_ids", None)
    return (
        1
        if (not _is_default(name) and not _is_default(aff) and not _is_default(pubids))
        else 0
    )


def _compute_paper_check(paper):
    title = getattr(paper, "title", None)
    abstract = getattr(paper, "abstract", None)
    pubdate = getattr(paper, "publication_date", None)
    doi = getattr(paper, "doi", None)
    pubtitle = getattr(paper, "publication_title", None)
    authors = getattr(paper, "authors", None)
    return (
        1
        if (
            not _is_default(title)
            and not _is_default(abstract)
            and not _is_default(pubdate)
            and not _is_default(doi)
            and not _is_default(pubtitle)
            and authors
            and len(authors) > 0
        )
        else 0
    )


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
