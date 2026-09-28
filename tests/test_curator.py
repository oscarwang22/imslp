from pathlib import Path

import pytest

from score_curator.compress import compress_ccitt_g4, validate_ccitt_g4
from score_curator.ethics import rights_allow
from score_curator.ledger import Ledger
from score_curator.review import next_pending, record_curator_selection


def candidate(file_id: str) -> dict:
    return {
        "file_id": file_id,
        "url": f"https://files.example/{file_id}.pdf",
        "description": "Complete score",
        "editor": "Editor",
        "publisher": "Publisher",
        "copyright": "Public Domain",
        "pages": 12,
        "downloads": 100,
        "rating": 4.5,
        "file_type": "score",
    }


def test_ccitt_group4_round_trip(tmp_path: Path) -> None:
    import fitz

    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    document = fitz.open()
    page = document.new_page(width=144, height=144)
    page.insert_text((20, 70), "Music")
    document.save(source)
    document.close()
    compress_ccitt_g4(source, output, dpi=100, threshold=190)
    validate_ccitt_g4(output, expected_pages=1)


def test_rights_gate_fails_closed_by_jurisdiction() -> None:
    assert rights_allow("Public Domain", "US")
    assert rights_allow("Creative Commons Attribution 4.0", "EU")
    assert not rights_allow("Public Domain - Non-PD US", "US")
    assert rights_allow("Public Domain - Non-PD US", "CA")
    assert not rights_allow("[TB] awaiting review", "CA")
    assert not rights_allow("", "EU")


def test_agent_selection_requires_distinct_known_files_and_reasons(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    ledger.initialize()
    work_url = "https://imslp.org/wiki/Example_(Composer,_Name)"
    ledger.append(
        "REVIEW_QUEUE.txt",
        {
            "url": work_url,
            "title": "Example",
            "composer": "Composer, Name",
            "candidates": [candidate("1"), candidate("2")],
        },
    )
    assert next_pending(ledger) is not None
    with pytest.raises(ValueError, match="distinct"):
        record_curator_selection(
            ledger,
            work_url=work_url,
            performance_id="1",
            performance_rationale="A complete and reliable performance text.",
            learning_id="1",
            learning_rationale="Clearly fingered and useful for close study.",
        )
    record_curator_selection(
        ledger,
        work_url=work_url,
        performance_id="1",
        performance_rationale="A complete and reliable performance text.",
        learning_id="2",
        learning_rationale="Clearly fingered and useful for close study.",
    )
    assert next_pending(ledger) is None
    decision = ledger.records("AGENT_SELECTIONS.txt")[0]
    assert decision["reviewer"] == "Arena.ai agent"
    assert decision["decision_method"].startswith("agent read all")
