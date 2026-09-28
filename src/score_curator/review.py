from __future__ import annotations

from .ledger import Ledger


def candidate_dossier(item: dict) -> str:
    lines = [
        f"WORK: {item['composer']} — {item['title']}",
        f"PAGE: {item['url']}",
        "",
        "The curator must read every candidate before choosing:",
    ]
    for candidate in item["candidates"]:
        lines.extend(
            [
                "-" * 78,
                f"FILE ID: {candidate['file_id']}",
                f"Description: {candidate.get('description') or '(not supplied)'}",
                f"Editor: {candidate.get('editor') or '(not supplied)'}",
                f"Publisher: {candidate.get('publisher') or '(not supplied)'}",
                f"Type: {candidate.get('file_type') or '(not supplied)'}",
                f"Pages: {candidate.get('pages') if candidate.get('pages') is not None else '(not supplied)'}",
                f"Rating: {candidate.get('rating') if candidate.get('rating') is not None else '(not supplied)'}",
                f"Downloads: {candidate.get('downloads') if candidate.get('downloads') is not None else '(not supplied)'}",
                f"Rights metadata: {candidate.get('copyright') or '(not supplied)'}",
                f"URL: {candidate['url']}",
            ]
        )
    return "\n".join(lines)


def next_pending(ledger: Ledger) -> dict | None:
    selected = {record["url"] for record in ledger.records("AGENT_SELECTIONS.txt")}
    return next(
        (record for record in ledger.records("REVIEW_QUEUE.txt") if record["url"] not in selected),
        None,
    )


def record_curator_selection(
    ledger: Ledger,
    *,
    work_url: str,
    performance_id: str,
    performance_rationale: str,
    learning_id: str,
    learning_rationale: str,
    reviewer: str = "Arena.ai agent",
) -> None:
    """Record the agent curator's considered decision; this function never recommends one."""
    matching = [record for record in ledger.records("REVIEW_QUEUE.txt") if record["url"] == work_url]
    if not matching:
        raise ValueError("work is not in REVIEW_QUEUE.txt")
    item = matching[-1]
    candidates = {candidate["file_id"] for candidate in item["candidates"]}
    if performance_id not in candidates or learning_id not in candidates:
        raise ValueError("both file IDs must belong to this work's eligible candidate list")
    if performance_id == learning_id:
        raise ValueError("performance and learning editions must be distinct")
    if len(performance_rationale.strip()) < 20 or len(learning_rationale.strip()) < 20:
        raise ValueError("each curator rationale must be substantive (at least 20 characters)")
    if work_url in {record["url"] for record in ledger.records("AGENT_SELECTIONS.txt")}:
        raise ValueError("work already has a recorded selection")
    ledger.append(
        "AGENT_SELECTIONS.txt",
        {
            "url": item["url"],
            "title": item["title"],
            "composer": item["composer"],
            "performance": {"file_id": performance_id, "rationale": performance_rationale.strip()},
            "learning": {"file_id": learning_id, "rationale": learning_rationale.strip()},
            "candidates": item["candidates"],
            "reviewer": reviewer,
            "decision_method": "agent read all collected edition metadata; no automatic ranking",
        },
    )
