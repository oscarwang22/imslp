WORKING LEDGERS
===============
These UTF-8 text files are append-only. Structured records are JSON Lines. They
make each bounded run auditable and resumable without hidden database state.

SEEDS.txt             seed pages and discovery counts
QUEUE.txt             work pages discovered from those seeds
VISITED.txt           metadata collection outcomes
REVIEW_QUEUE.txt      complete candidate metadata for the Arena agent to read
AGENT_SELECTIONS.txt Arena agent choices and substantive written rationales
DOWNLOADS.txt         output paths, byte counts, and SHA-256 hashes
RIGHTS_REVIEW.txt     ambiguous or rejected rights metadata
ERRORS.txt            recoverable errors
RUNS.txt              bounded-run start and finish summaries

The software must never populate AGENT_SELECTIONS.txt by scoring or ranking.
Only the reviewing agent records a decision after reading every listed edition.
Do not erase failures or rights-review entries merely to force a download.
