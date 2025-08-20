from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IEEEAuthor:
    author_id: str = ""
    name: str = ""
    affiliation: list[str] = field(default_factory=list)
    publication_ids: list[str] = field(default_factory=list)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, IEEEAuthor):
            return NotImplemented
        return self.author_id == value.author_id

    def check(self) -> bool:
        return bool(self.author_id and self.name)


@dataclass
class PaperMetaData:
    id: str = ""
    title: str = ""
    abstract: str = ""
    authors: list[IEEEAuthor] = field(default_factory=list)
    publication_date: datetime = field(default_factory=datetime.now)
    doi: str = ""
    publication_title: str = ""

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PaperMetaData):
            return NotImplemented
        return self.doi == value.doi

    def check(self) -> bool:
        if not (self.id and self.title and self.doi):
            return False
        if not self.authors or not all(
            isinstance(a, IEEEAuthor) and a.check() for a in self.authors
        ):
            return False
        if not isinstance(self.publication_date, datetime):
            return False
        return True
