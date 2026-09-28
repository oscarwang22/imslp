from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup

from .ethics import PoliteClient
from .models import Candidate, Work

API = "https://imslp.org/api.php"
WORK_TITLE = re.compile(r"^.+\([^()]+,\s*[^()]+\)$")
FILE_ID = re.compile(r"(?:ImagefromIndex/|#)(\d+)", re.IGNORECASE)
NUMBER = re.compile(r"([\d,]+)")


def page_title(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname not in {"imslp.org", "www.imslp.org"} or not parsed.path.startswith("/wiki/"):
        raise ValueError("not an IMSLP wiki URL")
    return unquote(parsed.path.removeprefix("/wiki/")).replace("_", " ")


def api_parse(client: PoliteClient, title: str, prop: str) -> dict:
    params = f"action=parse&format=json&formatversion=2&prop={quote(prop)}&page={quote(title)}"
    return client.get(f"{API}?{params}").json()["parse"]


def discover_work_urls(client: PoliteClient, seed_url: str) -> list[str]:
    """Use exactly the supplied page as the initial discovery frontier."""
    parsed = api_parse(client, page_title(seed_url), "links")
    urls = []
    for link in parsed.get("links", []):
        title = link.get("title", "")
        if link.get("ns") == 0 and WORK_TITLE.match(title) and not title.startswith(("IMSLP:", "Help:")):
            urls.append("https://imslp.org/wiki/" + quote(title.replace(" ", "_"), safe="(),:_'-"))
    return sorted(set(urls))


def _integer(text: str) -> int | None:
    match = NUMBER.search(text)
    return int(match.group(1).replace(",", "")) if match else None


def parse_work_html(html: str, url: str, fallback_title: str = "") -> Work:
    """Parse rendered file cards conservatively; unrecognised cards are ignored, not guessed."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    title_text = (heading.get_text(" ", strip=True) if heading else fallback_title) or page_title(url)
    match = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", title_text)
    title, composer = (match.group(1), match.group(2)) if match else (title_text, "Unknown")
    candidates: list[Candidate] = []

    for card in soup.select(".we_file, .we_file_entry, [data-imslp-id]"):
        link = card.select_one(
            'a[href*="ImagefromIndex"], a[href*="ReverseLookup"], a[href$=".pdf"], a[href*=".pdf?"]'
        )
        if link is None or not link.get("href"):
            continue
        href = link["href"]
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://imslp.org" + href
        text = " ".join(card.stripped_strings)
        id_match = FILE_ID.search(href)
        file_id = card.get("data-imslp-id") or (id_match.group(1) if id_match else href.rsplit("/", 1)[-1])
        copyright_node = card.select_one(".we_file_copyright, [class*='copyright']")
        editor_node = card.select_one(".we_file_editor, [class*='editor']")
        publisher_node = card.select_one(".we_file_publisher, [class*='publisher']")
        description_node = card.select_one(".we_file_title, .we_file_description")
        pages_match = re.search(r"(\d+)\s+pages?", text, re.IGNORECASE)
        downloads_match = re.search(r"([\d,]+)\s+downloads?", text, re.IGNORECASE)
        rating_match = re.search(r"rating\D+(\d(?:\.\d+)?)", text, re.IGNORECASE)
        candidates.append(
            Candidate(
                file_id=str(file_id),
                url=href,
                description=(description_node.get_text(" ", strip=True) if description_node else link.get_text(" ", strip=True)),
                editor=(editor_node.get_text(" ", strip=True) if editor_node else ""),
                publisher=(publisher_node.get_text(" ", strip=True) if publisher_node else ""),
                copyright=(copyright_node.get_text(" ", strip=True) if copyright_node else text),
                pages=int(pages_match.group(1)) if pages_match else None,
                downloads=_integer(downloads_match.group(1)) if downloads_match else None,
                rating=float(rating_match.group(1)) if rating_match else None,
                file_type="parts" if re.search(r"\bparts?\b", text, re.IGNORECASE) else "score",
            )
        )
    return Work(title=title.strip(), composer=composer.strip(), page_url=url, candidates=candidates)


def fetch_work(client: PoliteClient, url: str) -> Work:
    title = page_title(url)
    parsed = api_parse(client, title, "text")
    return parse_work_html(parsed.get("text", ""), url, parsed.get("title", title))
