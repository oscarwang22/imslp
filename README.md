# Score Curator

A cautious IMSLP curation workflow in which the **Arena agent—not a ranking
algorithm and not the end user—reviews every edition dossier** and chooses two
distinct editions of each work:

- **performance**: the edition the agent judges best for reliable performance;
- **learning**: the edition the agent judges best for study and learning.

Collection is automated only where it is clerical (link discovery, metadata
capture, downloading, compression, and validation). Edition selection is not.
The agent must read all collected metadata and write a substantive rationale for
each decision to `working/AGENT_SELECTIONS.txt`.

The initial configured project starts at Chopin's composer category and processes
10 works per bounded batch. That seed page, rather than a site-wide index, is the
source of newly discovered work pages.

## Ethical boundary

The project uses IMSLP's documented MediaWiki API, honors `robots.txt` and its
2-second crawl delay, identifies itself, sends requests serially, and stops on
rate limiting. It never logs in, defeats a wait timer, follows a hidden route, or
bypasses a membership/interstitial page. Unknown, blocked, `[TB]`, copyrighted,
or jurisdiction-excluded files fail closed into `RIGHTS_REVIEW.txt`.

Downloads require `download = true`, an explicit rights acknowledgement, and a
prior agent-authored selection. IMSLP metadata is not legal advice; copyright
must be checked in the configured jurisdiction.

## Workflow

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
score-curator init

score-curator discover       # links from the configured seed only
score-curator collect        # metadata dossiers; no recommendation or score
score-curator next-dossier   # agent reads every edition in the next work
```

After independently comparing all metadata, the agent records two distinct IDs
and its reasons:

```bash
score-curator record-selection \
  --url 'https://imslp.org/wiki/...' \
  --performance-id 123456 \
  --performance-rationale 'Specific evidence-based reason...' \
  --learning-id 234567 \
  --learning-rationale 'Specific evidence-based reason...'
```

There is deliberately no default, heuristic score, or automatic fallback. The
command checks that both IDs belong to that work, are distinct, and have
substantive rationales. Once an agent-reviewed batch is complete:

```bash
# First set download = true after rights review.
score-curator archive --acknowledge-rights
```

An Arena agent can repeat `collect` → dossier review → `record-selection` →
`archive` in later turns. It cannot continue making subjective decisions while
no agent turn is running; the append-only ledgers preserve the exact frontier so
work resumes without pretending a background heuristic is a reviewer.

## File structure

```text
library/
  frederic-chopin/
    COMPOSER.txt
    <work>/
      WORK.txt
      performance/
        score.pdf
        PROVENANCE.txt
      learning/
        score.pdf
        PROVENANCE.txt
working/
  SEEDS.txt                 # discovery roots
  QUEUE.txt                 # discovered work pages
  VISITED.txt               # metadata collection outcomes
  REVIEW_QUEUE.txt          # full eligible-edition dossiers
  AGENT_SELECTIONS.txt     # agent choices and written reasons
  DOWNLOADS.txt             # paths, sizes, and SHA-256 hashes
  RIGHTS_REVIEW.txt         # ambiguous/rejected rights metadata
  ERRORS.txt                # recoverable errors
  RUNS.txt                  # bounded batch summaries
```

All operational state is inspectable UTF-8 text (JSON Lines where structured).
Generated composer directories and PDFs are excluded from Git.

## CCITT Group 4

Every source page is rendered at 300 DPI, converted deterministically to 1-bit
without dithering, stored as a Group 4 TIFF, and embedded losslessly in a new PDF.
The validator checks each image XObject for `/CCITTFaxDecode` and `/K -1` and
checks the page count before replacing the output atomically.

```bash
score-curator compress legally-obtained.pdf output.pdf --dpi 300 --threshold 190
score-curator validate output.pdf
```

This intentionally removes colour, vectors, links, and selectable text. The
agent should visually inspect faint or dirty scores and adjust threshold when
needed.

## Development

```bash
pytest
ruff check .
```

Tests use local fixtures and do not create unsolicited IMSLP traffic.
