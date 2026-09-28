from __future__ import annotations

from dataclasses import asdict

from .archive import download_and_archive, write_metadata
from .config import Config
from .discovery import discover_work_urls, fetch_work
from .ethics import PolicyError, PoliteClient, rights_allow
from .ledger import Ledger
from .models import Candidate, Selection, Work


def discover(config: Config) -> int:
    ledger = Ledger(config.working_dir)
    ledger.initialize()
    known = ledger.known_urls("QUEUE.txt") | ledger.known_urls("VISITED.txt")
    with PoliteClient(config.contact, config.request_delay_seconds) as client:
        urls = discover_work_urls(client, config.seed_url)
    ledger.append("SEEDS.txt", {"url": config.seed_url, "discovered": len(urls)})
    new_urls = [url for url in urls if url not in known]
    for url in new_urls:
        ledger.append("QUEUE.txt", {"url": url, "source": config.seed_url})
    return len(new_urls)


def collect(config: Config) -> dict[str, int]:
    """Collect metadata only. Deliberately makes no edition recommendation."""
    ledger = Ledger(config.working_dir)
    ledger.initialize()
    if not ledger.records("QUEUE.txt"):
        discover(config)
    visited = ledger.known_urls("VISITED.txt")
    queued = [record["url"] for record in ledger.records("QUEUE.txt") if record["url"] not in visited]
    queued = queued[: config.max_works_per_run]
    summary = {"collected": 0, "rights_review": 0, "errors": 0}
    ledger.append("RUNS.txt", {"event": "collect_start", "limit": config.max_works_per_run})

    with PoliteClient(config.contact, config.request_delay_seconds) as client:
        for url in queued:
            try:
                work = fetch_work(client, url)
                eligible = [
                    candidate
                    for candidate in work.candidates
                    if candidate.file_type == "score"
                    and rights_allow(candidate.copyright, config.jurisdiction)
                ]
                rejected = [candidate.file_id for candidate in work.candidates if candidate not in eligible]
                if rejected:
                    ledger.append(
                        "RIGHTS_REVIEW.txt",
                        {"url": url, "jurisdiction": config.jurisdiction, "file_ids": rejected},
                    )
                if len(eligible) < 2:
                    summary["rights_review"] += 1
                    ledger.append(
                        "RIGHTS_REVIEW.txt",
                        {
                            "url": url,
                            "reason": "fewer than two unambiguously eligible score editions",
                            "eligible": len(eligible),
                        },
                    )
                    status = "rights_review"
                else:
                    ledger.append(
                        "REVIEW_QUEUE.txt",
                        {
                            "url": url,
                            "title": work.title,
                            "composer": work.composer,
                            "candidates": [asdict(candidate) for candidate in eligible],
                            "instruction": "read every candidate; manually choose two distinct editions",
                        },
                    )
                    summary["collected"] += 1
                    status = "awaiting_manual_review"
                ledger.append("VISITED.txt", {"url": url, "status": status})
            except (ValueError, KeyError, OSError, PolicyError, RuntimeError) as error:
                summary["errors"] += 1
                ledger.append("ERRORS.txt", {"url": url, "error": type(error).__name__, "detail": str(error)})
    ledger.append("RUNS.txt", {"event": "collect_finish", **summary})
    return summary


def archive_reviewed(config: Config, *, acknowledge_rights: bool = False) -> dict[str, int]:
    """Archive only decisions explicitly written by the reviewing Arena agent."""
    if not config.download or not acknowledge_rights:
        raise ValueError("archive requires download=true and --acknowledge-rights")
    ledger = Ledger(config.working_dir)
    ledger.initialize()
    already = {record.get("work_url") for record in ledger.records("DOWNLOADS.txt")}
    decisions = [r for r in ledger.records("AGENT_SELECTIONS.txt") if r["url"] not in already]
    summary = {"archived": 0, "errors": 0}
    with PoliteClient(config.contact, config.request_delay_seconds) as client:
        for decision in decisions[: config.max_works_per_run]:
            try:
                candidates = {raw["file_id"]: Candidate(**raw) for raw in decision["candidates"]}
                work = Work(decision["title"], decision["composer"], decision["url"], list(candidates.values()))
                selections = []
                for purpose in ("performance", "learning"):
                    manual = decision[purpose]
                    candidate = candidates[manual["file_id"]]
                    if not rights_allow(candidate.copyright, config.jurisdiction):
                        raise ValueError(f"rights metadata no longer passes for {candidate.file_id}")
                    selections.append(Selection(purpose, candidate, None, (manual["rationale"],)))
                write_metadata(work, config.output_dir)
                for selection in selections:
                    download_and_archive(
                        client,
                        ledger,
                        work,
                        selection,
                        config.output_dir,
                        max_bytes=config.max_download_megabytes * 1024 * 1024,
                        dpi=config.render_dpi,
                        threshold=config.threshold,
                    )
                # A separate terminal marker prevents one successful work being downloaded twice.
                ledger.append("DOWNLOADS.txt", {"work_url": decision["url"], "status": "work_complete"})
                summary["archived"] += 1
            except (ValueError, KeyError, OSError, PolicyError, RuntimeError) as error:
                summary["errors"] += 1
                ledger.append(
                    "ERRORS.txt",
                    {"url": decision["url"], "error": type(error).__name__, "detail": str(error)},
                )
    return summary
