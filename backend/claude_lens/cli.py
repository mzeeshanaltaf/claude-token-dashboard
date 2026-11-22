"""claude-lens command line entry point."""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import __version__


def _not_implemented(args: argparse.Namespace) -> int:
    print(f"claude-lens {args.command}: not implemented")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-lens",
        description="Claude Lens: usage, cost & workflow analytics for Claude Code.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    commands = {
        "scan": "Ingest new JSONL transcript lines into Postgres.",
        "migrate-sqlite": "Copy history from the old SQLite database into Postgres.",
        "status": "Show sync status and database counts.",
        "set-password": "Reset the admin password.",
    }
    for name, help_text in commands.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=_not_implemented)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
