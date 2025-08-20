from datetime import datetime
from playwright.sync_api import Browser, Page, ElementHandle
import utils
import T
import typing
import logging


def goto_with_retry(page: Page, url: str, max_retries=3):
    def _goto():
        return page.goto(url, wait_until="load")

    return utils.retry_with_exponential_backoff(_goto, max_retries=max_retries)


def get_next_sibling_element(el: ElementHandle) -> typing.Optional[ElementHandle]:
    """
    Return the next sibling element of the given ElementHandle, or None if not present.
    Usage:
        next_el = get_next_sibling_element(some_el)
        if next_el:
            text = next_el.inner_text()
    """
    if el is None:
        return None
    try:
        js_handle = el.evaluate_handle("e => e.nextElementSibling")
        if js_handle:
            next_el = js_handle.as_element()
            return next_el
    except Exception:
        return None
    return None


class PublicationPage:
    def __init__(self, browser: Browser, publication_id: str, logger: logging.Logger):
        self.browser = browser
        self.publication_id = publication_id
        self.pub_url = f"https://ieeexplore.ieee.org/document/{publication_id}"
        self.logger = logger

    def fetch_info(self) -> typing.Optional[T.PaperMetaData]:
        ea = False
        try:
            self.logger.info(f"Opening publication page: {self.pub_url}")
            with self.browser.new_page() as page:
                goto_with_retry(page, self.pub_url)
                self.logger.debug("Page loaded, waiting randomly.")
                utils.random_wait(page, min_seconds=2, max_seconds=4)
                assert utils.has_access(page), "Access to the page is not available."
                self.logger.info("Access confirmed.")

                publication_info = T.PaperMetaData(
                    id=self.publication_id,
                )
                el_title = page.query_selector("h1.document-title")
                if el_title:
                    publication_info.title = el_title.inner_text()
                    self.logger.debug(f"Title extracted: {publication_info.title}")

                btn_expand_abstract = page.query_selector(
                    "a.document-abstract-toggle-btn"
                )
                if btn_expand_abstract:
                    btn_expand_abstract.click()
                    self.logger.debug("Clicked abstract expand button.")
                el_ab_parent = page.query_selector("div.abstract-text div.u-mb-1")
                if el_ab_parent:
                    divs = el_ab_parent.query_selector_all("div")
                    if divs:
                        publication_info.abstract = divs[0].inner_text()
                        self.logger.debug(
                            f"Abstract extracted: {publication_info.abstract}"
                        )

                el_pub_title = page.query_selector(
                    "a.stats-document-abstract-publishedIn"
                )
                if el_pub_title:
                    publication_info.publication_title = el_pub_title.inner_text()
                    self.logger.debug(
                        f"Publication title: {publication_info.publication_title}"
                    )
                    # check if Early Access
                    el_ea = get_next_sibling_element(el_pub_title)
                    if el_ea:
                        ea = "Early" in el_ea.inner_text()
                        if ea:
                            self.logger.debug("Publication is Early Access.")
                    else:
                        self.logger.debug("Publication is not Early Access.")

                el_doi_link = page.query_selector("div.stats-document-abstract-doi a")
                if el_doi_link:
                    publication_info.doi = el_doi_link.inner_text()
                    self.logger.debug(f"DOI: {publication_info.doi}")

                el_pub_date = page.query_selector("div.doc-abstract-pubdate")
                if el_pub_date:
                    date_str = utils.remove_none(el_pub_date.inner_text(), "")
                    publication_info.publication_date = datetime.strptime(
                        date_str.split(":")[-1].strip(),
                        "%d %B %Y",
                    )
                    self.logger.debug(
                        f"Publication date: {publication_info.publication_date}"
                    )

                btn_expand_author = page.query_selector("button#authors")
                if btn_expand_author:
                    btn_expand_author.click()
                    self.logger.debug("Clicked author expand button.")
                    utils.random_wait(page)
                el_authors = page.query_selector_all("div.authors-accordion-container")
                self.logger.info(f"Found {len(el_authors)} authors.")

                # here is a ugly patch, because there are different layout for maybe
                # if the paper is in Early Access, if not, author picture will be displayed
                qk = "col-14-24" if ea == "" else "col-24-24"
                for el_author in el_authors:
                    author_info = T.IEEEAuthor(name="", affiliation=[], author_id="")
                    el_author_name = el_author.query_selector(f"div.{qk} a")
                    if el_author_name:
                        author_info.name = el_author_name.inner_text()
                        author_id = el_author_name.get_attribute("href")
                        author_info.author_id = utils.remove_none(author_id, "").split(
                            "/"
                        )[-1]
                        self.logger.debug(
                            f"Author name: {author_info.name}, ID: {author_info.author_id}"
                        )
                    el_col = el_author.query_selector(f"div.{qk}")
                    if el_col:
                        first_level_divs = el_col.query_selector_all(":scope > div")
                        for div in first_level_divs[1:]:
                            child_divs = div.query_selector_all("div")
                            author_info.affiliation = [
                                child.inner_text() for child in child_divs if child
                            ]
                        self.logger.debug(
                            f"Author affiliation: {author_info.affiliation}"
                        )
                    publication_info.authors.append(author_info)

            self.logger.info("Publication info extraction completed.")
            return publication_info
        except Exception as e:
            self.logger.error(f"Error fetching publication info: {e}", exc_info=True)
            return None


class AuthorPage:
    def __init__(self, browser: Browser, author_id: str, logger: logging.Logger):
        self.browser = browser
        self.author_id = author_id
        self.url = f"https://ieeexplore.ieee.org/author/{author_id}?"
        self.logger = logger
        self._page = None  # 缓存页面对象

    def _get_or_open_page(self):
        if self._page is None or self._page.is_closed():
            self.logger.info(f"Opening author page: {self.url}")
            self._page = self.browser.new_page()
            goto_with_retry(self._page, self.url)
            self.logger.debug("Page loaded, waiting randomly.")
            utils.random_wait(self._page)
            assert utils.has_access(self._page), "Access to the page is not available."
            self.logger.info("Access confirmed.")
        return self._page

    def get_author_info(self) -> typing.Optional[T.IEEEAuthor]:
        try:
            page = self._get_or_open_page()
            author_info = T.IEEEAuthor(author_id=self.author_id)
            el_name = page.query_selector(".u-pr-02")
            if el_name:
                author_info.name = el_name.inner_text()
                self.logger.debug(f"Author name: {author_info.name}")
            el_affiliation_parent = page.query_selector("div.current-affiliation div")
            if el_affiliation_parent:
                divs = el_affiliation_parent.query_selector_all("div")
                author_info.affiliation = [div.inner_text() for div in divs if div]
                self.logger.debug(f"Author affiliation: {author_info.affiliation}")

            self.logger.info("Author info extraction completed.")
            return author_info
        except Exception as e:
            self.logger.error(f"Error fetching author info: {e}", exc_info=True)
            return None

    def get_published_work_id_list(
        self,
        start_year: typing.Optional[int] = None,
        end_year: typing.Optional[int] = None,
    ) -> list[str]:
        ids = []
        try:
            page = self._get_or_open_page()
            self.logger.info(
                f"Using cached author page for publication list: {self.url}"
            )

            if start_year is not None and end_year is not None:
                self.logger.info(
                    f"Filtering publications from {start_year} to {end_year}"
                )
                page.get_by_role("textbox", name="Enter start year of range").fill(
                    str(start_year)
                )
                page.get_by_role("textbox", name="Enter end year of range").fill(
                    str(end_year)
                )

                btn = page.query_selector("#Year-apply-btn")
                assert btn is not None, "Year apply button not found."
                btn.click()
                self.logger.debug("Clicked year apply button.")
                utils.random_wait(page, min_seconds=4, max_seconds=8)

            while True:
                divs = page.query_selector_all("div.List-results-items")
                ids += [utils.remove_none(div.get_attribute("id"), "") for div in divs]
                self.logger.info(f"Collected {len(ids)} published works so far.")
                next_btn = page.query_selector("li.next-btn button")
                if next_btn and next_btn.is_enabled():
                    self.logger.debug("Next page button found, clicking to continue.")
                    next_btn.click()
                    utils.random_wait(page, min_seconds=2, max_seconds=4)
                else:
                    self.logger.debug(
                        "No next page button found or button disabled, stop paging."
                    )
                    break
            self.logger.info(f"Found {len(ids)} published works in total.")
            return ids

        except Exception as e:
            self.logger.error(f"Error fetching published work: {e}", exc_info=True)
            return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self._page and not self._page.is_closed():
            self._page.close()
            self._page = None


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)

    pub = PublicationPage(browser, "11124431", logger)

    # info = pub.fetch_info()
    # print(info)

    # with open("test.json", "w") as f:
    #     json.dump(
    #         asdict(
    #             utils.remove_none(info, T.PaperMetaData()),
    #         ),
    #         f,
    #     )
    author = AuthorPage(browser, "37290266200", logger)

    pub_list = author.get_published_work_id_list(2024, 2025)

    print(pub_list)
