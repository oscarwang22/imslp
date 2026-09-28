from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Config:
    seed_url: str
    output_dir: Path = Path("library")
    working_dir: Path = Path("working")
    jurisdiction: str = "US"
    contact: str = ""
    request_delay_seconds: float = 2.5
    max_works_per_run: int = 10
    max_download_megabytes: int = 250
    render_dpi: int = 300
    threshold: int = 190
    download: bool = False

    @classmethod
    def load(cls, path: Path) -> Config:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        for key in ("output_dir", "working_dir"):
            if key in raw:
                raw[key] = Path(raw[key])
        config = cls(**raw)
        config.validate()
        return config

    def validate(self) -> None:
        parsed = urlparse(self.seed_url)
        if parsed.scheme != "https" or parsed.hostname not in {"imslp.org", "www.imslp.org"}:
            raise ValueError("seed_url must be an https://imslp.org/wiki/... URL")
        if not parsed.path.startswith("/wiki/"):
            raise ValueError("seed_url must be a normal /wiki/ page")
        if self.jurisdiction not in {"US", "CA", "EU"}:
            raise ValueError("jurisdiction must be US, CA, or EU")
        if self.request_delay_seconds < 2:
            raise ValueError("request_delay_seconds cannot be below IMSLP's 2-second crawl delay")
        if not 1 <= self.max_works_per_run <= 100:
            raise ValueError("max_works_per_run must be between 1 and 100")
        if not self.contact or not ("@" in self.contact or self.contact.startswith("https://")):
            raise ValueError("set contact to a monitored email or project URL for the User-Agent")
        if not 72 <= self.render_dpi <= 600 or not 0 <= self.threshold <= 255:
            raise ValueError("render_dpi or threshold is outside the safe range")
