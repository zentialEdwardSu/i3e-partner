import sqlite3
import json
from datetime import datetime
import typing
import os
import logging
from T import IEEEAuthor, PaperMetaData
import utils

raise NotImplementedError("SQlite3 based Database backend is deprecated.")
# Switching to 2 backend, the duckdb one and the tinydb one, the current implementation will be removed in future versions.


# get database path from environment variable
DB_PATH = os.environ.get("DB_PATH", "ieee.db")

# New: default sqlite timeout and retry settings
_DEFAULT_SQLITE_TIMEOUT = 30  # seconds for sqlite connect busy timeout
_MAX_LOCK_RETRIES = 5
_BASE_BACKOFF = 0.2  # seconds


def get_conn(
    db_path: typing.Optional[str] = None, timeout: int = _DEFAULT_SQLITE_TIMEOUT
):
    """
    Return a sqlite3.Connection with safe pragmas (WAL, busy_timeout) and given timeout.
    """
    path = db_path or DB_PATH
    # allow other threads to use same connection if necessary; set timeout to wait for locks
    conn = sqlite3.connect(path, timeout=timeout, check_same_thread=False)
    try:
        # Enable WAL to reduce writer/readers locking contention
        conn.execute("PRAGMA journal_mode=WAL;")
        # set synchronous to NORMAL for performance (can be adjusted)
        conn.execute("PRAGMA synchronous=NORMAL;")
        # busy timeout in ms
        conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")
    except Exception:
        # If pragmas fail, ignore and continue with connection
        pass
    return conn


def init_db(
    db_path: typing.Optional[str] = None, logger: typing.Optional[logging.Logger] = None
):
    """
    Initialize the SQLite database and create necessary tables if they do not exist.
    Args:
        db_path (str): Optional database path.
        logger (logging.Logger): Optional logger to use.
    """
    logger = logger or logging.getLogger(__name__)
    logger.info(f"Initializing database at {db_path or DB_PATH}")
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS author (
            author_id TEXT PRIMARY KEY,
            name TEXT,
            affiliation TEXT,
            publication_ids TEXT,
            "check" INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper (
            id TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            publication_date TEXT,
            doi TEXT UNIQUE,
            publication_title TEXT,
            "check" INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_author (
            paper_id TEXT,
            author_id TEXT,
            PRIMARY KEY (paper_id, author_id)
        )
    """)
    # ensure older DBs get the new columns if missing (safe to ignore failure)
    try:
        c.execute('ALTER TABLE author ADD COLUMN "check" INTEGER')
    except Exception:
        pass
    try:
        c.execute('ALTER TABLE paper ADD COLUMN "check" INTEGER')
    except Exception:
        pass
    c.execute("CREATE INDEX IF NOT EXISTS idx_author_id ON author(author_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_doi ON paper(doi)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_author_name ON author(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_paper_title ON paper(title)")
    conn.commit()
    conn.close()
    logger.info("Database initialized.")


def _choose_value(field_name: str, old, new, strategy: str) -> typing.Any:
    """
    Decide which value to keep for a single field according to strategy.
    AO: keep old
    AN: use new
    M: ask user
    """
    if utils._is_default(old) and not utils._is_default(new):
        return new
    if utils._is_default(new) and not utils._is_default(old):
        return old
    if old == new:
        return old
    strategy = (strategy or "AN").upper()
    if strategy == "AO":
        return old
    if strategy == "AN":
        return new
    # Manual
    while True:
        try:
            resp = (
                input(
                    f"Conflict for '{field_name}':\n  old={old!r}\n  new={new!r}\nChoose (o)ld/(n)ew: "
                )
                .strip()
                .lower()
            )
        except Exception:
            resp = "o"
        if resp in ("o", "old", ""):
            return old
        if resp in ("n", "new"):
            return new
        print("Please enter 'o' or 'n'.")


def save_or_update_author(
    author: IEEEAuthor,
    db_path: typing.Optional[str] = None,
    strategy: str = "AN",
    aconn: typing.Optional[sqlite3.Connection] = None,
    logger: typing.Optional[logging.Logger] = None,
):
    """
    Insert or update an author.
    - If not exists: insert.
    - If exists: for each field (name, affiliation, publication_ids),
      apply overwrite rules:
        * if old is default -> take new
        * if new is default -> keep old
        * else use strategy: AO/AN/M
    """
    logger = logger or logging.getLogger(__name__)
    logger.debug(f"Upserting author {author.author_id} with strategy={strategy}")
    conn = aconn or get_conn(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT author_id, name, affiliation, publication_ids FROM author WHERE author_id=?",
        (author.author_id,),
    )
    row = c.fetchone()
    author_checked = utils._compute_author_check(author)
    if not row:
        logger.info(f"Author {author.author_id} not found, inserting.")
        c.execute(
            """
            INSERT INTO author (author_id, name, affiliation, publication_ids, "check")
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                author.author_id,
                author.name,
                json.dumps(getattr(author, "affiliation", [])),
                json.dumps(getattr(author, "publication_ids", [])),
                author_checked,
            ),
        )
        conn.commit()
        if aconn is None:
            conn.close()
        logger.info(f"Author {author.author_id} inserted.")
        return

    # exists -> compare and decide
    old_name = row[1]
    try:
        old_aff = json.loads(row[2]) if row[2] else []
    except Exception:
        old_aff = []
    try:
        old_pub_ids = json.loads(row[3]) if row[3] else []
    except Exception:
        old_pub_ids = []

    # decide per-field
    name_chosen = _choose_value("name", old_name, author.name, strategy)
    aff_chosen = _choose_value(
        "affiliation", old_aff, getattr(author, "affiliation", []), strategy
    )
    pubids_chosen = _choose_value(
        "publication_ids", old_pub_ids, getattr(author, "publication_ids", []), strategy
    )

    # compute chosen checked value based on chosen fields
    chosen_author = IEEEAuthor(
        author_id=author.author_id, name=name_chosen, affiliation=aff_chosen
    )
    try:
        chosen_author.publication_ids = pubids_chosen
    except Exception:
        pass
    chosen_checked = utils._compute_author_check(chosen_author)

    # update if any change
    if (
        name_chosen != old_name
        or aff_chosen != old_aff
        or pubids_chosen != old_pub_ids
        or chosen_checked != (row[3] if len(row) > 3 else 0)
    ):
        logger.info(f"Updating author {author.author_id}")
        c.execute(
            'UPDATE author SET name=?, affiliation=?, publication_ids=?, "check"=? WHERE author_id=?',
            (
                name_chosen,
                json.dumps(aff_chosen),
                json.dumps(pubids_chosen),
                chosen_checked,
                author.author_id,
            ),
        )
        conn.commit()
        logger.debug(f"Author {author.author_id} updated.")
    else:
        logger.debug(f"No changes for author {author.author_id}.")

    if aconn is None:  # if we create a conn close it, else just do nothing
        conn.close()


# keep backward-compatible save_author calling the new function (default AN)
def save_author(author: IEEEAuthor, db_path: typing.Optional[str] = None):
    return save_or_update_author(author, db_path=db_path, strategy="AN")


def save_paper(
    paper: PaperMetaData,
    db_path: typing.Optional[str] = None,
    strategy: str = "AN",
    logger: typing.Optional[logging.Logger] = None,
):
    """
    Save or update a paper and its authors.
    Strategy applies when updating existing paper fields and author upserts.
    """
    logger = logger or logging.getLogger(__name__)
    logger.debug(f"Saving paper {paper.id} with strategy={strategy}")
    conn = get_conn(db_path)
    c = conn.cursor()
    # check existing paper
    c.execute(
        "SELECT id, title, abstract, publication_date, doi, publication_title FROM paper WHERE id=?",
        (paper.id,),
    )
    row = c.fetchone()
    paper_checked = utils._compute_paper_check(paper)
    if not row:
        logger.info(f"Inserting new paper {paper.id}")
        c.execute(
            """
            INSERT INTO paper (id, title, abstract, publication_date, doi, publication_title, "check")
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                paper.id,
                paper.title,
                paper.abstract,
                paper.publication_date.isoformat()
                if isinstance(paper.publication_date, datetime)
                else (
                    str(paper.publication_date)
                    if paper.publication_date is not None
                    else None
                ),
                paper.doi,
                paper.publication_title,
                paper_checked,
            ),
        )
    else:
        logger.info(
            f"Paper {paper.id} exists, resolving conflicts with strategy={strategy}"
        )
        # existing -> compare fields and decide
        old_title = row[1]
        old_abstract = row[2]
        old_pubdate = row[3]
        old_doi = row[4]
        old_pubtitle = row[5]

        # normalize incoming pubdate to iso string or None
        new_pubdate = None
        if isinstance(paper.publication_date, datetime):
            new_pubdate = paper.publication_date.isoformat()
        elif paper.publication_date is not None:
            new_pubdate = str(paper.publication_date)

        title_chosen = _choose_value("title", old_title, paper.title, strategy)
        abstract_chosen = _choose_value(
            "abstract", old_abstract, paper.abstract, strategy
        )
        pubdate_chosen = _choose_value(
            "publication_date", old_pubdate, new_pubdate, strategy
        )
        doi_chosen = _choose_value("doi", old_doi, paper.doi, strategy)
        pubtitle_chosen = _choose_value(
            "publication_title", old_pubtitle, paper.publication_title, strategy
        )

        c.execute(
            'UPDATE paper SET title=?, abstract=?, publication_date=?, doi=?, publication_title=?, "check"=? WHERE id=?',
            (
                title_chosen,
                abstract_chosen,
                pubdate_chosen,
                doi_chosen,
                pubtitle_chosen,
                utils._compute_paper_check(
                    PaperMetaData(
                        id=paper.id,
                        title=title_chosen,
                        abstract=abstract_chosen,
                        authors=getattr(paper, "authors", []),
                        doi=doi_chosen,
                        publication_title=pubtitle_chosen,
                        publication_date=(
                            datetime.fromisoformat(pubdate_chosen)
                            if pubdate_chosen
                            else datetime.now()
                        ),
                    )
                ),
                paper.id,
            ),
        )
        logger.debug(f"Paper {paper.id} fields chosen and updated.")

    logger.info(f"Paper {paper.id} saved/updated.")
    # upsert authors and paper_author relations
    for author in getattr(paper, "authors", []):
        # retry-wrapped author upsert to handle locks
        save_or_update_author(
            author, db_path=db_path, strategy=strategy, logger=logger, aconn=conn
        )
        c.execute(
            """
            INSERT OR IGNORE INTO paper_author (paper_id, author_id)
            VALUES (?, ?)
            """,
            (paper.id, author.author_id),
        )
    conn.commit()
    conn.close()


# provide an update_paper wrapper for compatibility (calls new save_paper with strategy)
def update_paper(
    paper_id: str, db_path: typing.Optional[str] = None, strategy: str = "AN", **kwargs
):
    """
    Update fields of a paper record in the database.
    Args:
        paper_id (str): The ID of the paper to update.
        db_path (str): Optional database path.
        **kwargs: Fields to update.
    """
    # This compatibility wrapper will fetch the paper, apply kwargs and call save_paper
    pm = get_paper_by_id(paper_id, db_path=db_path)
    if pm is None:
        # nothing to update, create minimal
        pm = PaperMetaData(
            id=paper_id,
        )
    # apply kwargs to pm
    for k, v in kwargs.items():
        if k == "publication_date" and isinstance(v, datetime):
            setattr(pm, k, v)
        else:
            setattr(pm, k, v)
    save_paper(pm, db_path=db_path, strategy=strategy)


def get_author_by_id(
    author_id: str,
    db_path: typing.Optional[str] = None,
    logger: typing.Optional[logging.Logger] = None,
) -> IEEEAuthor | None:
    """
    Retrieve an author by their ID.
    Args:
        author_id (str): The ID of the author.
        db_path (str): Optional database path.
    Returns:
        IEEEAuthor or None: The author object if found, else None.
    """
    logger = logger or logging.getLogger(__name__)
    logger.debug(f"Query author by id: {author_id}")
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        'SELECT author_id, name, affiliation, publication_ids, "check" FROM author WHERE author_id=?',
        (author_id,),
    )
    row = c.fetchone()
    conn.close()
    if row:
        aff = json.loads(row[2]) if row[2] else []
        pub_ids = json.loads(row[3]) if row[3] else []
        author = IEEEAuthor(row[0], row[1], aff)
        try:
            author.publication_ids = pub_ids
        except Exception:
            pass
        try:
            author.check = int(row[4]) if row[4] is not None else 0
        except Exception:
            pass
        return author
    return None


def get_author_by_name(
    name: str, db_path: typing.Optional[str] = None
) -> list[IEEEAuthor]:
    """
    Retrieve authors whose names match the given string.
    Args:
        name (str): The name or partial name to search for.
        db_path (str): Optional database path.
    Returns:
        list[IEEEAuthor]: List of matching authors.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT author_id, name, affiliation, publication_ids FROM author WHERE name LIKE ?",
        (f"%{name}%",),
    )
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        aff = json.loads(r[2]) if r[2] else []
        pub_ids = json.loads(r[3]) if r[3] else []
        author = IEEEAuthor(r[0], r[1], aff)
        try:
            author.publication_ids = pub_ids
        except Exception:
            pass
        result.append(author)
    return result


def get_paper_by_doi(
    doi: str, db_path: typing.Optional[str] = None
) -> PaperMetaData | None:
    """
    Retrieve a paper by its DOI.
    Args:
        doi (str): The DOI of the paper.
        db_path (str): Optional database path.
    Returns:
        PaperMetaData or None: The paper object if found, else None.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT id, title, abstract, publication_date, doi, publication_title FROM paper WHERE doi=?",
        (doi,),
    )
    paper_row = c.fetchone()
    if not paper_row:
        conn.close()
        return None
    c.execute("SELECT author_id FROM paper_author WHERE paper_id=?", (paper_row[0],))
    author_ids = [r[0] for r in c.fetchall()]
    authors = [
        a
        for a in (get_author_by_id(aid, db_path=db_path) for aid in author_ids)
        if a is not None
    ]
    conn.close()
    pm = PaperMetaData(
        paper_row[0],
        paper_row[1],
        paper_row[2],
        authors,
        paper_row[4],
        paper_row[5],
    )
    if paper_row[3]:
        pm.publication_date = datetime.fromisoformat(paper_row[3])

    return pm


def get_paper_by_id(
    paper_id: str, db_path: typing.Optional[str] = None
) -> PaperMetaData | None:
    """
    Retrieve a paper by its ID.
    Args:
        paper_id (str): The ID of the paper.
        db_path (str): Optional database path.
    Returns:
        PaperMetaData or None: The paper object if found, else None.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        'SELECT id, title, abstract, publication_date, doi, publication_title, "check" FROM paper WHERE id=?',
        (paper_id,),
    )
    paper_row = c.fetchone()
    if not paper_row:
        conn.close()
        return None
    c.execute("SELECT author_id FROM paper_author WHERE paper_id=?", (paper_row[0],))
    author_ids = [r[0] for r in c.fetchall()]
    authors = [
        a
        for a in (get_author_by_id(aid, db_path=db_path) for aid in author_ids)
        if a is not None
    ]
    conn.close()
    pm = PaperMetaData(
        paper_row[0],
        paper_row[1],
        paper_row[2],
        authors,
        paper_row[4],
        paper_row[5],
    )
    if paper_row[3]:
        pm.publication_date = datetime.fromisoformat(paper_row[3])
    try:
        pm.check = int(paper_row[6]) if paper_row[6] is not None else 0
    except Exception:
        pass

    return pm


def get_paper_by_title(
    title: str, db_path: typing.Optional[str] = None
) -> list[PaperMetaData]:
    """
    Retrieve papers whose titles match the given string.
    Args:
        title (str): The title or partial title to search for.
        db_path (str): Optional database path.
    Returns:
        list[PaperMetaData]: List of matching papers.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT id, title, abstract, publication_date, doi, publication_title FROM paper WHERE title LIKE ?",
        (f"%{title}%",),
    )
    papers = []
    for paper_row in c.fetchall():
        c2 = get_conn(db_path)
        c2_cur = c2.cursor()
        c2_cur.execute(
            "SELECT author_id FROM paper_author WHERE paper_id=?", (paper_row[0],)
        )
        author_ids = [r[0] for r in c2_cur.fetchall()]
        authors = [
            a
            for a in (get_author_by_id(aid, db_path=db_path) for aid in author_ids)
            if a is not None
        ]
        c2.close()
        pm = PaperMetaData(
            paper_row[0],
            paper_row[1],
            paper_row[2],
            authors,
            paper_row[4],
            paper_row[5],
        )
        if paper_row[3]:
            pm.publication_date = datetime.fromisoformat(paper_row[3])
        papers.append(pm)

    conn.close()
    return papers


def get_papers_by_author_id(
    author_id: str, db_path: typing.Optional[str] = None
) -> list[PaperMetaData]:
    """
    Retrieve all papers written by the author with the given ID.
    Args:
        author_id (str): The IEEE ID of the author.
        db_path (str): Optional database path.
    Returns:
        list[PaperMetaData]: List of papers authored by the given author.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT paper_id FROM paper_author WHERE author_id=?",
        (author_id,),
    )
    paper_ids = [r[0] for r in c.fetchall()]
    papers = [get_paper_by_id(pid, db_path=db_path) for pid in paper_ids]
    conn.close()
    return [p for p in papers if p is not None]


def get_papers_by_author_name(
    name: str, db_path: typing.Optional[str] = None
) -> list[PaperMetaData]:
    """
    Retrieve all papers written by authors whose names match the given string.
    Args:
        name (str): The name or partial name to search for.
        db_path (str): Optional database path.
    Returns:
        list[PaperMetaData]: List of papers authored by matching authors.
    """
    authors = get_author_by_name(name, db_path=db_path)
    papers = []
    for author in authors:
        papers.extend(get_papers_by_author_id(author.author_id, db_path=db_path))
    return papers


def get_authors_by_paper_id(
    paper_id: str, db_path: typing.Optional[str] = None
) -> list[IEEEAuthor]:
    """
    Retrieve all authors of a paper by the paper's ID.
    Args:
        paper_id (str): The ID of the paper.
        db_path (str): Optional database path.
    Returns:
        list[IEEEAuthor]: List of authors for the given paper.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT author_id FROM paper_author WHERE paper_id=?", (paper_id,))
    author_ids = [r[0] for r in c.fetchall()]
    conn.close()
    authors = []
    for aid in author_ids:
        author = get_author_by_id(aid, db_path=db_path)
        if author is not None:
            authors.append(author)
    return authors


def export_db(
    json_path: str,
    db_path: typing.Optional[str] = None,
    logger: typing.Optional[logging.Logger] = None,
):
    """
    Export all authors and papers in the database to a JSON file.
    Args:
        json_path (str): The path to the output JSON file.
        db_path (str): Optional database path.
    """
    logger = logger or logging.getLogger(__name__)
    logger.info(f"Exporting DB to {json_path} (db_path={db_path or DB_PATH})")
    conn = get_conn(db_path)
    c = conn.cursor()
    # Export authors
    c.execute(
        'SELECT author_id, name, affiliation, publication_ids, "check" FROM author'
    )
    authors = [
        {
            "author_id": row[0],
            "name": row[1],
            "affiliation": json.loads(row[2]) if row[2] else [],
            "publication_ids": json.loads(row[3]) if row[3] else [],
            "check": int(row[4]) if row[4] is not None else 0,
        }
        for row in c.fetchall()
    ]
    # Export papers
    c.execute(
        'SELECT id, title, abstract, publication_date, doi, publication_title, "check" FROM paper'
    )
    papers = []
    for paper_row in c.fetchall():
        c.execute(
            "SELECT author_id FROM paper_author WHERE paper_id=?", (paper_row[0],)
        )
        author_ids = [r[0] for r in c.fetchall()]
        papers.append(
            {
                "id": paper_row[0],
                "title": paper_row[1],
                "abstract": paper_row[2],
                "publication_date": paper_row[3],
                "doi": paper_row[4],
                "publication_title": paper_row[5],
                "check": int(paper_row[6]) if paper_row[6] is not None else 0,
                "authors": author_ids,
            }
        )
    conn.close()
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"authors": authors, "papers": papers}, f, ensure_ascii=False, indent=2
        )
    logger.info(f"Exported DB to {json_path}")


def get_all_authors(db_path: typing.Optional[str] = None) -> list[IEEEAuthor]:
    """
    Retrieve all authors from the database.
    Args:
        db_path (str): Optional database path.
    Returns:
        list[IEEEAuthor]: List of all authors.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        'SELECT author_id, name, affiliation, publication_ids, "check" FROM author'
    )
    rows = c.fetchall()
    conn.close()
    authors = []
    for r in rows:
        aff = json.loads(r[2]) if r[2] else []
        pub_ids = json.loads(r[3]) if r[3] else []
        author = IEEEAuthor(r[0], r[1], aff)
        try:
            author.publication_ids = pub_ids
        except Exception:
            pass
        try:
            author.check = int(r[4]) if r[4] is not None else 0
        except Exception:
            pass
        authors.append(author)
    return authors


def get_all_papers(db_path: typing.Optional[str] = None) -> list[PaperMetaData]:
    """
    Retrieve all papers from the database.
    Args:
        db_path (str): Optional database path.
    Returns:
        list[PaperMetaData]: List of all papers.
    """
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        'SELECT id, title, abstract, publication_date, doi, publication_title, "check" FROM paper'
    )
    papers = []
    for paper_row in c.fetchall():
        c.execute(
            "SELECT author_id FROM paper_author WHERE paper_id=?", (paper_row[0],)
        )
        author_ids = [r[0] for r in c.fetchall()]
        authors = [
            a
            for a in (get_author_by_id(aid, db_path=db_path) for aid in author_ids)
            if a is not None
        ]
        pm = PaperMetaData(
            paper_row[0],
            paper_row[1],
            paper_row[2],
            authors,
            paper_row[4],
            paper_row[5],
        )
        if paper_row[3]:
            pm.publication_date = datetime.fromisoformat(paper_row[3])
        try:
            pm.check = int(paper_row[6]) if paper_row[6] is not None else 0
        except Exception:
            pass
        papers.append(pm)
    conn.close()
    return papers


def get_unchecked_authors(db_path: typing.Optional[str] = None) -> list[str]:
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute('SELECT author_id FROM author WHERE "check" IS NULL OR "check" != 1')
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def get_unchecked_papers(db_path: typing.Optional[str] = None) -> list[str]:
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute('SELECT id FROM paper WHERE "check" IS NULL OR "check" != 1')
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows
