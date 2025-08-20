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
