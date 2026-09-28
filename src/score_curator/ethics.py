from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Self
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx


class PolicyError(RuntimeError):
    pass


@dataclass
class PoliteClient:
    contact: str
    delay: float = 2.5
    timeout: float = 45

    def __post_init__(self) -> None:
        self.user_agent = f"ScoreCurator/0.1 (research; contact={self.contact})"
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._last_request = 0.0
        self._robots: dict[str, RobotFileParser] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _pace(self) -> None:
        remaining = self.delay - (time.monotonic() - self._last_request)
        if remaining > 0:
            time.sleep(remaining)

    def _robots_for(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            robots_url = urljoin(origin, "/robots.txt")
            self._pace()
            try:
                response = self._client.get(robots_url)
            except httpx.HTTPError as error:
                raise PolicyError(f"could not retrieve robots.txt safely: {error}") from error
            self._last_request = time.monotonic()
            parser = RobotFileParser(robots_url)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                # A missing robots file permits access under the standard. We still pace.
                parser.parse([])
            self._robots[origin] = parser
        return self._robots[origin]

    def get(self, url: str, *, enforce_robots: bool = True) -> httpx.Response:
        if enforce_robots and not self._robots_for(url).can_fetch(self.user_agent, url):
            raise PolicyError(f"robots.txt does not permit automated access to {url}")
        self._pace()
        try:
            response = self._client.get(url)
        except httpx.HTTPError as error:
            raise PolicyError(f"request failed: {error}") from error
        self._last_request = time.monotonic()
        if response.status_code == 429:
            raise PolicyError(f"rate limited; Retry-After={response.headers.get('Retry-After', 'unknown')}")
        response.raise_for_status()
        return response


def rights_allow(status: str, jurisdiction: str) -> bool:
    """Conservative gate. Ambiguous, blocked, and jurisdiction-excluded files fail closed."""
    text = " ".join(status.lower().split())
    if not text or any(term in text for term in ("[tb]", "blocked", "copyrighted", "unknown")):
        return False
    exclusions = {
        "US": ("non-pd us", "not public domain in the usa", "non-pd usa"),
        "CA": ("non-pd ca", "not public domain in canada"),
        "EU": ("non-pd eu", "not public domain in the eu"),
    }
    if any(term in text for term in exclusions[jurisdiction]):
        return False
    return "public domain" in text or "creative commons" in text or "cc by" in text
