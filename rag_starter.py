"""Small CLI over the same Python/LangChain backend used by the dashboard.

By default this uses .studybook-script/, separate from dashboard data.
Ingest/list/search use no chat model. ask/generate call the configured local model.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from backend.core import AppError, NotebookStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Studybook: local multi-document RAG")
    parser.add_argument("--data-dir", type=Path, default=Path(".studybook-script"))
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Parse and index files locally")
    ingest.add_argument("files", type=Path, nargs="+")
    commands.add_parser("list", help="Show document IDs and source metadata")
    for name in ("search", "ask"):
        command = commands.add_parser(name, help="Retrieve excerpts" if name == "search" else "Ask the local chat model")
        command.add_argument("question")
        command.add_argument("--source", action="append", help="Document ID; repeat for a selection. Default: all documents.")
    generate = commands.add_parser("generate", help="Generate study material with the local model")
    generate.add_argument("kind", choices=["summary", "study_guide", "flashcards", "quiz"])
    generate.add_argument("--source", action="append", help="Document ID; default: all documents")
    args = parser.parse_args()
    store = NotebookStore(args.data_dir)
    try:
        if args.command == "ingest":
            result = [store.ingest(path.name, path.read_bytes()) for path in args.files]
        elif args.command == "list":
            result = store.list_documents()
        else:
            selected = args.source if args.source is not None else [doc["id"] for doc in store.list_documents()]
            if args.command == "search":
                result = [{"text": doc.page_content, "source": doc.metadata} for doc in store.retrieve(args.question, selected)]
            elif args.command == "ask":
                result = store.chat(args.question, selected, history=[])
            else:
                result = store.generate(args.kind, selected)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (AppError, OSError) as exc:
        print(f"Studybook: {exc}", file=sys.stderr)
        return 1
    finally:
        asyncio.run(store.http_async_client.aclose())
        store.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
