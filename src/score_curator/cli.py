from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .compress import compress_ccitt_g4, validate_ccitt_g4
from .config import Config
from .ledger import Ledger
from .pipeline import archive_reviewed, collect, discover
from .review import candidate_dossier, next_pending, record_curator_selection


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="score-curator", description="Agent-reviewed IMSLP curator")
    root.add_argument("--config", type=Path, default=Path("config.toml"))
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create config and append-only working ledgers")
    commands.add_parser("discover", help="discover work links from the configured seed page")
    commands.add_parser("collect", help="collect metadata dossiers; never rank editions")
    commands.add_parser("next-dossier", help="print all metadata for the next agent review")
    select = commands.add_parser("record-selection", help="record the agent curator's considered choice")
    select.add_argument("--url", required=True)
    select.add_argument("--performance-id", required=True)
    select.add_argument("--performance-rationale", required=True)
    select.add_argument("--learning-id", required=True)
    select.add_argument("--learning-rationale", required=True)
    archive_parser = commands.add_parser("archive", help="download only agent-selected editions")
    archive_parser.add_argument("--acknowledge-rights", action="store_true", required=True)
    compress_parser = commands.add_parser("compress", help="convert one local PDF to CCITT Group 4")
    compress_parser.add_argument("source", type=Path)
    compress_parser.add_argument("destination", type=Path)
    compress_parser.add_argument("--dpi", type=int, default=300)
    compress_parser.add_argument("--threshold", type=int, default=190)
    validate_parser = commands.add_parser("validate", help="verify every page image uses CCITT Group 4")
    validate_parser.add_argument("pdf", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "init":
        if not args.config.exists():
            example = Path(__file__).resolve().parents[2] / "config.example.toml"
            if not example.exists():
                example = Path("config.example.toml")
            shutil.copyfile(example, args.config)
            print(f"Created {args.config}; review jurisdiction and limits before running.")
        else:
            print(f"Kept existing {args.config}.")
        Ledger(Path("working")).initialize()
        return 0
    if args.command == "compress":
        compress_ccitt_g4(args.source, args.destination, dpi=args.dpi, threshold=args.threshold)
        print(args.destination)
        return 0
    if args.command == "validate":
        validate_ccitt_g4(args.pdf)
        print(f"OK: {args.pdf} uses CCITT Group 4 on every page")
        return 0

    config = Config.load(args.config)
    ledger = Ledger(config.working_dir)
    ledger.initialize()
    if args.command == "discover":
        print(f"Queued {discover(config)} new work pages")
        return 0
    if args.command == "collect":
        summary = collect(config)
    elif args.command == "next-dossier":
        item = next_pending(ledger)
        if item is None:
            print("No edition dossier is awaiting agent review.")
            return 1
        print(candidate_dossier(item))
        return 0
    elif args.command == "record-selection":
        record_curator_selection(
            ledger,
            work_url=args.url,
            performance_id=args.performance_id,
            performance_rationale=args.performance_rationale,
            learning_id=args.learning_id,
            learning_rationale=args.learning_rationale,
        )
        print("Recorded agent curator selection.")
        return 0
    else:
        summary = archive_reviewed(config, acknowledge_rights=args.acknowledge_rights)
    print(json.dumps(summary, sort_keys=True))
    return 0 if not summary["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
