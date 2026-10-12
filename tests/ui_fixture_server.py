r"""Temporary, explicitly fake browser-QA server. Never imported by production.

Run from the project root:
    .venv\Scripts\python.exe tests\ui_fixture_server.py --port 8766

The library lives in an isolated temporary directory. Model generation is replaced
only for this process, and both model HTTP transports reject every request without
opening sockets. This fixture does not prove actual model generation works.
"""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

# Direct script invocation places tests/, rather than the project, on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import uvicorn

from backend.core import NotebookStore
from backend.main import create_app


FIXTURE_MARKDOWN = """# Offline UI test fixture

This deterministic response was produced by the temporary browser test fixture.
It is **not model output** and does not verify actual inference.

## Overview

Open the source citation to inspect the selected document excerpt. [S1]
This deliberately invalid source tests rejection: [S999].

## Learning objectives

- Inspect the source reader and page or chunk location.
- Verify Markdown formatting, studio saving, and local export.

## Core concepts

The sample notebook is original demonstration material. Inspect its cited passage
before treating any statement as supported. [S1]

## Key terms

**Citation:** a link to an excerpt supplied to the response renderer. [S1]

## Worked examples

1. Open the valid citation.
2. Return to the notebook.
3. Export this visibly labeled fixture as Markdown.

## Practice questions

What kind of response is this? **Answer:** an offline UI test fixture.

## Flashcards

### Card 1

**Front:** Does this fixture verify actual model generation?

**Back:** No. It exercises the notebook interface with deterministic test text. [S1]

## Questions

1. What does the source citation open?

## Answer key

1. A passage from the selected local source. [S1]

## Review checklist

- [ ] Open a source citation.
- [ ] Open the saved studio artifact.
- [ ] Export and inspect its Markdown.

## Coverage notes

This is fixture text used only for browser verification. Unknown source markers
must appear as unverified and must never create a source link.
"""


def reject_model_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"UI fixture forbids model HTTP requests: {request.method} {request.url.path}")


def create_fixture_app(data_dir: str):
    app = create_app(data_dir=data_dir)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def fixture_lifespan(application):
        with patch.dict(os.environ, {
            "STUDYBOOK_EMBEDDING_MODE": "lexical",
            "STUDYBOOK_BASE_URL": "http://127.0.0.1:8090/v1",
            "STUDYBOOK_MODEL": "offline-ui-fixture",
        }), patch.object(NotebookStore, "invoke", lambda _self, _messages: FIXTURE_MARKDOWN):
            async with original_lifespan(application):
                store = application.state.store
                store.http_client.close()
                await store.http_async_client.aclose()
                transport = httpx.MockTransport(reject_model_request)
                store.http_client = httpx.Client(transport=transport, trust_env=False, follow_redirects=False)
                store.http_async_client = httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False)
                for name in (
                    "01-learning-plan.md",
                    "02-glossary-notebook.md",
                    "03-interpreting-practice.md",
                ):
                    example = PROJECT_ROOT / "examples" / name
                    store.ingest(name, example.read_bytes())
                yield

    app.router.lifespan_context = fixture_lifespan
    return app


def main():
    parser = argparse.ArgumentParser(description="Temporary offline Studybook browser test fixture")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535.")
    with tempfile.TemporaryDirectory(prefix="studybook-ui-fixture-", ignore_cleanup_errors=True) as directory:
        print("OFFLINE UI FIXTURE: responses are fake, sources are temporary, model requests are blocked.")
        uvicorn.run(create_fixture_app(directory), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
