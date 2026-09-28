from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HEADERS = {
    "SEEDS.txt": "# ISO timestamp | seed page\n",
    "QUEUE.txt": "# JSON Lines: discovered work-page frontier\n",
    "VISITED.txt": "# JSON Lines: pages fetched successfully\n",
    "REVIEW_QUEUE.txt": "# JSON Lines: complete metadata dossiers awaiting agent review\n",
    "AGENT_SELECTIONS.txt": "# JSON Lines: agent curator choices and written rationales\n",
    "DOWNLOADS.txt": "# JSON Lines: source, destination, bytes, and SHA-256\n",
    "ERRORS.txt": "# JSON Lines: recoverable failures\n",
    "RUNS.txt": "# JSON Lines: start/end summaries and configuration\n",
    "RIGHTS_REVIEW.txt": (
        "# Items rejected or requiring human copyright review. No legal conclusion is implied.\n"
    ),
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Ledger:
    """Append-only, inspectable text ledgers; JSONL makes restarts deterministic."""

    def __init__(self, root: Path):
        self.root = root

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name, header in HEADERS.items():
            path = self.root / name
            if not path.exists():
                path.write_text(header, encoding="utf-8")

    def append(self, name: str, event: dict[str, Any]) -> None:
        if name not in HEADERS:
            raise ValueError(f"unknown ledger: {name}")
        payload = {"at": now(), **event}
        with (self.root / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    def records(self, name: str) -> list[dict[str, Any]]:
        path = self.root / name
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                records.append(json.loads(line))
        return records

    def known_urls(self, name: str) -> set[str]:
        return {r["url"] for r in self.records(name) if "url" in r}
