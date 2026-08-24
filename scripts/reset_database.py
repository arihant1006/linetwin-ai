#!/usr/bin/env python
"""Delete the digital-twin SQLite database (including -wal/-shm sidecar files)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.data import database  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Reset (delete) the digital-twin database at "
                    "<repo>/data/digitaltwin.db or $DIGITALTWIN_DB.")
    ap.add_argument("--yes", action="store_true",
                    help="skip the interactive confirmation prompt")
    args = ap.parse_args(argv)

    target = database.resolve_db_path()

    if not args.yes and sys.stdin.isatty():
        answer = input(f"Delete database {target} (+ '-wal'/-'shm' sidecars)? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Aborted - nothing deleted.")
            return 1

    path = database.reset_db()
    print(f"Database deleted and re-initialized (empty schema) at: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
