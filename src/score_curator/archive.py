from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .compress import compress_ccitt_g4
from .ethics import PoliteClient
from .ledger import Ledger
from .models import Selection, Work


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "unknown"


def write_metadata(work: Work, root: Path) -> Path:
    directory = root / slug(work.composer) / slug(work.title)
    directory.mkdir(parents=True, exist_ok=True)
    composer_file = directory.parent / "COMPOSER.txt"
    if not composer_file.exists():
        composer_file.write_text(f"Composer: {work.composer}\n", encoding="utf-8")
    (directory / "WORK.txt").write_text(
        f"Title: {work.title}\nComposer: {work.composer}\nSource page: {work.page_url}\n",
        encoding="utf-8",
    )
    return directory


def download_and_archive(
    client: PoliteClient,
    ledger: Ledger,
    work: Work,
    selection: Selection,
    root: Path,
    *,
    max_bytes: int,
    dpi: int,
    threshold: int,
) -> Path:
    directory = write_metadata(work, root) / selection.purpose
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / "score.pdf"
    if final.exists():
        return final

    response = client.get(selection.candidate.url)
    content_type = response.headers.get("content-type", "").lower()
    data = response.content
    if len(data) > max_bytes:
        raise ValueError(f"download exceeds configured cap ({len(data)} > {max_bytes})")
    if not data.startswith(b"%PDF-") and "application/pdf" not in content_type:
        raise ValueError("download endpoint did not return a PDF (no wait-page bypass attempted)")

    source = directory / ".source.pdf"
    source.write_bytes(data)
    try:
        compress_ccitt_g4(source, final, dpi=dpi, threshold=threshold)
    finally:
        source.unlink(missing_ok=True)
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    provenance = {
        "work_page": work.page_url,
        "purpose": selection.purpose,
        "selection": selection.as_dict(),
        "output_sha256": digest,
        "compression": {"codec": "CCITT Group 4", "dpi": dpi, "threshold": threshold},
    }
    (directory / "PROVENANCE.txt").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ledger.append(
        "DOWNLOADS.txt",
        {"url": selection.candidate.url, "path": str(final), "bytes": len(data), "sha256": digest},
    )
    return final
