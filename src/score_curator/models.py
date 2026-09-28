from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Candidate:
    file_id: str
    url: str
    description: str = ""
    editor: str = ""
    publisher: str = ""
    copyright: str = ""
    pages: int | None = None
    downloads: int | None = None
    rating: float | None = None
    file_type: str = "score"


@dataclass
class Work:
    title: str
    composer: str
    page_url: str
    candidates: list[Candidate] = field(default_factory=list)


@dataclass(frozen=True)
class Selection:
    purpose: str
    candidate: Candidate
    score: float | None
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        return result
