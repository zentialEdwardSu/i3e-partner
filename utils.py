import random
from playwright.sync_api import Page
from playwright.sync_api import Error
import typing

T = typing.TypeVar("T")


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
